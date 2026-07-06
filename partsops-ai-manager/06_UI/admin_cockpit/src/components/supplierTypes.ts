export type SupplierRecord = {
  supplier_id: string;
  name: string;
  contact_person: string;
  phone: string;
  email: string;
  city: string;
  specialization: string;
  reliability_score: number;
  avg_delivery_days: number;
  status: string;
  rating_manual: number | null;
  rating_auto: number;
  account_owner: string;
  payment_terms: string;
  delivery_terms: string;
  currency_default: string;
  notes_internal: string;
  last_feed_at: string | null;
  last_sync_status: string;
  categories: string[];
  table_count: number;
  active_table_count: number;
  last_activity_at: string | null;
};

export type SupplierTableRecord = {
  table_id: string;
  supplier_id: string;
  name: string;
  source_type: string;
  filename: string;
  version: number;
  status: string;
  uploaded_at: string;
  uploaded_by: string;
  row_count: number;
  mapped_columns_json: Record<string, string>;
  validation_summary_json: Record<string, unknown>;
  is_active: boolean;
};

export type SupplierTableRowRecord = {
  row_key: string;
  part_name: string;
  oem_number: string;
  brand: string;
  price: number;
  currency: string;
  stock_qty: number;
  delivery_days: number;
  category: string;
  raw_payload_json: Record<string, unknown>;
};

export type SupplierLogRecord = {
  event_id: string;
  supplier_id: string;
  table_id: string | null;
  event_type: string;
  actor_id: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type SupplierAnalyticsRecord = {
  supplier_id: string;
  summary: {
    table_count: number;
    active_table_count: number;
    catalog_item_count: number;
    avg_price: number;
    avg_delivery_days: number;
    manual_rating: number | null;
    auto_rating: number;
    stale_table_count: number;
    avg_price_deviation: number;
  };
  reliability_history: Array<{
    logged_at: string;
    reliability_score: number;
    event_type: string;
    reason: string | null;
  }>;
  category_coverage: Array<{
    category: string;
    count: number;
  }>;
  table_health: Array<{
    table_id: string;
    name: string;
    status: string;
    is_active: boolean;
    row_count: number;
  }>;
};
