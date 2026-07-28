"""
PartsOps AI Manager v3 — PDF Invoice & Delivery Channels (Phase 5).

Implements:
- InvoicePDFGenerator: Generates PDF invoice using reportlab (fallback to formatted HTML/text).
- sanitize_for_delivery: Cleans text against prompt-injection (forget all, ignore previous instructions, etc.).
- EmailAdapter: Queues and dispatches email notifications.
- TelegramAdapter: Queues and dispatches telegram notifications.

OutboundMessage statuses: pending -> sent / failed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from models import OutboundMessage, PartRequest, RequestState, EventType
from suppliers import Invoice
from event_store import emit_event

# ──────────────────────────────────────────────
# PDF Generator
# ──────────────────────────────────────────────

class InvoicePDFGenerator:
    """Generates print-ready PDF invoices from structured DB models."""
    
    @staticmethod
    def generate(invoice: Invoice) -> bytes:
        """
        Generate invoice content.
        Uses reportlab if available; otherwise falls back to a clean, structured HTML/text representation.
        Returns bytes representing the document content.
        """
        # Try importing reportlab
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib import colors
            import io
            
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=30,
                leftMargin=30,
                topMargin=30,
                bottomMargin=30,
            )
            styles = getSampleStyleSheet()
            story = []
            
            # Header
            story.append(Paragraph(f"<b>SCHET / INVOICE #{invoice.invoice_number}</b>", styles["Title"]))
            story.append(Spacer(1, 10))
            story.append(Paragraph(f"Date: {invoice.created_at.strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
            story.append(Paragraph(f"Customer: {invoice.customer_name}", styles["Normal"]))
            story.append(Spacer(1, 20))
            
            # Items Table
            items_data = [["Part Name", "Brand", "OEM", "Qty", "Price", "Total"]]
            
            raw_items = json.loads(invoice.items_json) if invoice.items_json else []
            for item in raw_items:
                items_data.append([
                    str(item.get("part_name", "")),
                    str(item.get("brand", "")),
                    str(item.get("oem_number", "")),
                    str(item.get("quantity", 1)),
                    f"{item.get('sale_price', 0):.2f}",
                    f"{item.get('line_total', 0):.2f}"
                ])
                
            t = Table(items_data)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
            ]))
            story.append(t)
            story.append(Spacer(1, 20))
            
            # Totals
            story.append(Paragraph(f"Subtotal: {invoice.subtotal:.2f} RUB", styles["Normal"]))
            story.append(Paragraph(f"Tax (VAT 20%): {invoice.tax:.2f} RUB", styles["Normal"]))
            story.append(Paragraph(f"<b>Total: {invoice.total:.2f} RUB</b>", styles["Normal"]))
            
            doc.build(story)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            return pdf_bytes
            
        except ImportError:
            # Fallback text/HTML representation
            lines = [
                f"=== INVOICE {invoice.invoice_number} ===",
                f"Date: {invoice.created_at.strftime('%Y-%m-%d %H:%M')}",
                f"Customer: {invoice.customer_name}",
                "-" * 40,
                f"{'Part Name':<25} | {'Qty':<4} | {'Price':<10} | {'Total':<10}",
                "-" * 40,
            ]
            raw_items = json.loads(invoice.items_json) if invoice.items_json else []
            for item in raw_items:
                lines.append(
                    f"{item.get('part_name', '')[:25]:<25} | "
                    f"{item.get('quantity', 1):<4} | "
                    f"{item.get('sale_price', 0):<10.2f} | "
                    f"{item.get('line_total', 0):<10.2f}"
                )
            lines.extend([
                "-" * 40,
                f"Subtotal: {invoice.subtotal:.2f} RUB",
                f"Tax: {invoice.tax:.2f} RUB",
                f"Total: {invoice.total:.2f} RUB",
                "========================="
            ])
            return "\n".join(lines).encode("utf-8")


# ──────────────────────────────────────────────
# Prompt Injection Safety Sanitize
# ──────────────────────────────────────────────

def sanitize_for_delivery(text: str) -> str:
    """
    Sanitizes string inputs to prevent prompt-injection attacks.
    Removes key command override phrases and script/HTML tag blocks.
    """
    if not text:
        return ""
    
    # Lowercase match check for known injection commands
    injection_patterns = [
        r"(?i)ignore\s+previous\s+instructions",
        r"(?i)system\s+override",
        r"(?i)forget\s+all",
        r"(?i)drop\s+table",
        r"(?i)delete\s+from",
        r"(?i)truncate\s+table",
        r"(?i)select\s+\*\s+from",
    ]
    
    sanitized = text
    for pattern in injection_patterns:
        sanitized = re.sub(pattern, "[CLEANED]", sanitized)
        
    # Strip HTML / scripts
    sanitized = re.sub(r"<[^>]*>", "", sanitized)
    
    return sanitized


# ──────────────────────────────────────────────
# Email Adapter
# ──────────────────────────────────────────────

class EmailAdapter:
    """Queues and sends email messages with PDF attachments."""
    
    @staticmethod
    def send_invoice(
        invoice: Invoice,
        recipient_email: str,
        session: Session,
        tenant_id: str = "default",
        dry_run: bool = False
    ) -> OutboundMessage:
        if os.getenv("PARTSOPS_ENV", "dev").strip().lower() in {"prod", "production"}:
            dry_run = False
        # Sanitize recipient and metadata
        safe_recipient = sanitize_for_delivery(recipient_email)
        safe_customer = sanitize_for_delivery(invoice.customer_name)
        
        # Generate PDF
        pdf_bytes = InvoicePDFGenerator.generate(invoice)
        pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
        
        subject = f"Invoice {invoice.invoice_number} from PartsOps"
        body_text = (
            f"Dear {safe_customer},\n\n"
            f"Please find attached your invoice {invoice.invoice_number} for the total amount of {invoice.total:.2f} RUB.\n\n"
            f"Best regards,\nPartsOps Team"
        )
        
        idempotency_key = f"email-invoice-{invoice.invoice_number}-{pdf_hash[:10]}"
        
        # Check if already queued/sent
        existing = session.exec(
            select(OutboundMessage).where(
                OutboundMessage.idempotency_key == idempotency_key,
                OutboundMessage.tenant_id == tenant_id,
            )
        ).first()
        if existing:
            return existing
            
        message = OutboundMessage(
            tenant_id=tenant_id,
            request_id=invoice.request_id,
            channel="email",
            recipient=safe_recipient,
            subject=subject,
            body_text=body_text,
            payload_json=json.dumps({
                "invoice_number": invoice.invoice_number,
                "pdf_hash": pdf_hash,
                "pdf_size": len(pdf_bytes),
            }),
            idempotency_key=idempotency_key,
            status="pending",
            attempts=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(message)
        session.flush()
        
        # Try to dispatch
        success = False
        error_msg = None
        
        if dry_run:
            success = True
            error_msg = "Dry-run: simulated send"
        else:
            # SMTP sending simulation/actual
            smtp_host = os.getenv("SMTP_HOST", "")
            if not smtp_host:
                error_msg = "SMTP_HOST not configured, treating as failed send"
            else:
                try:
                    import smtplib
                    from email.mime.multipart import MIMEMultipart
                    from email.mime.text import MIMEText
                    from email.mime.base import MIMEBase
                    from email import encoders
                    
                    msg = MIMEMultipart()
                    msg['From'] = os.getenv("SMTP_USER", "noreply@partsops.com")
                    msg['To'] = safe_recipient
                    msg['Subject'] = subject
                    msg.attach(MIMEText(body_text, 'plain'))
                    
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(pdf_bytes)
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f"attachment; filename=Invoice-{invoice.invoice_number}.pdf")
                    msg.attach(part)
                    
                    # Connect and send
                    server = smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "587")))
                    server.starttls()
                    server.login(os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASSWORD", ""))
                    server.sendmail(msg['From'], safe_recipient, msg.as_string())
                    server.quit()
                    success = True
                except Exception as e:
                    error_msg = str(e)
                    
        message.attempts += 1
        if success:
            message.status = "sent"
            message.sent_at = datetime.utcnow()
        else:
            message.status = "failed"
            message.last_error = error_msg
            
        message.updated_at = datetime.utcnow()
        session.add(message)
        
        # Emit event
        emit_event(
            session,
            invoice.request_id,
            EventType.DOCUMENT_PARSED if success else EventType.ERP_SYNC_FAILED, # Fallback type or generic alert
            actor_type="system",
            actor_id="delivery_email",
            payload={
                "channel": "email",
                "invoice_number": invoice.invoice_number,
                "recipient": safe_recipient,
                "pdf_hash": pdf_hash,
                "status": message.status,
                "error": error_msg,
            },
            tenant_id=tenant_id,
            commit=False
        )
        
        session.commit()
        return message


# ──────────────────────────────────────────────
# Telegram Adapter
# ──────────────────────────────────────────────

class TelegramAdapter:
    """Queues and sends telegram messages with attachments."""
    
    @staticmethod
    def send_invoice_preview(
        invoice: Invoice,
        chat_id: str,
        session: Session,
        tenant_id: str = "default",
        dry_run: bool = False
    ) -> OutboundMessage:
        if os.getenv("PARTSOPS_ENV", "dev").strip().lower() in {"prod", "production"}:
            dry_run = False
        safe_chat_id = sanitize_for_delivery(chat_id)
        safe_customer = sanitize_for_delivery(invoice.customer_name)
        
        pdf_bytes = InvoicePDFGenerator.generate(invoice)
        pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
        
        body_text = (
            f"🧾 *Счет № {invoice.invoice_number}* для {safe_customer}\n"
            f"Сумма: {invoice.total:.2f} RUB\n"
            f"Позиций: {len(json.loads(invoice.items_json) if invoice.items_json else [])}\n\n"
            f"PDF-счет подготовлен к отправке."
        )
        
        idempotency_key = f"tg-invoice-{invoice.invoice_number}-{pdf_hash[:10]}"
        
        existing = session.exec(
            select(OutboundMessage).where(
                OutboundMessage.idempotency_key == idempotency_key,
                OutboundMessage.tenant_id == tenant_id,
            )
        ).first()
        if existing:
            return existing
            
        message = OutboundMessage(
            tenant_id=tenant_id,
            request_id=invoice.request_id,
            channel="telegram",
            recipient=safe_chat_id,
            body_text=body_text,
            payload_json=json.dumps({
                "invoice_number": invoice.invoice_number,
                "pdf_hash": pdf_hash,
            }),
            idempotency_key=idempotency_key,
            status="pending",
            attempts=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(message)
        session.flush()
        
        success = False
        error_msg = None
        
        if dry_run:
            success = True
            error_msg = "Dry-run: simulated telegram send"
        else:
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            if not bot_token:
                error_msg = "TELEGRAM_BOT_TOKEN not configured"
            else:
                try:
                    import httpx
                    from concurrent.futures import ThreadPoolExecutor
                    
                    # 1. Send text preview
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    r = httpx.post(url, json={
                        "chat_id": safe_chat_id,
                        "text": body_text,
                        "parse_mode": "Markdown"
                    }, timeout=10.0, limits=httpx.Limits(max_connections=50, max_keepalive_connections=10))
                    
                    if r.status_code == 200:
                        # 2. Send PDF document
                        doc_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
                        files = {"document": (f"Invoice-{invoice.invoice_number}.pdf", pdf_bytes)}
                        doc_r = httpx.post(doc_url, data={"chat_id": safe_chat_id}, files=files, timeout=15.0, limits=httpx.Limits(max_connections=50, max_keepalive_connections=10))
                        if doc_r.status_code == 200:
                            success = True
                        else:
                            error_msg = f"Failed sending document: {doc_r.text[:300]}"
                    else:
                        error_msg = f"Failed sending message: {r.text[:300]}"
                except Exception as e:
                    error_msg = str(e)
                    
        message.attempts += 1
        if success:
            message.status = "sent"
            message.sent_at = datetime.utcnow()
        else:
            message.status = "failed"
            message.last_error = error_msg
            
        message.updated_at = datetime.utcnow()
        session.add(message)
        session.commit()
        return message
