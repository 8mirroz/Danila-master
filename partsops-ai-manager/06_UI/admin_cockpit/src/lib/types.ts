export type RequestItem = {
  id: number;
  request_id: string;
  source: string;
  status: string;
  customer_name: string;
  priority?: string;
  created_at?: string;
  parts_json: string;
};

export type Request = {
  id: number;
  request_id: string;
  source: string;
  status: string;
  customer_name: string;
  created_at: string;
  parts_json: string;
  customer_phone_masked?: string;
  customer_email_masked?: string;
  vehicle_vin_masked?: string;
  priority?: string;
  vehicle_make?: string;
  vehicle_model?: string;
  erp_quotation_ref?: string | null;
  erp_invoice_ref?: string | null;
  allowed_targets?: string[];
  allowed_actions?: Array<{ id: string; kind: string; target_state?: string }>;
  recommended_action?: { id: string; kind: string; target_state?: string } | null;
  is_blocked?: boolean;
};
