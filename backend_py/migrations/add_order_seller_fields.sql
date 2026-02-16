-- Order: seller revision comment and done_at (run if columns don't exist)
ALTER TABLE orders ADD COLUMN IF NOT EXISTS seller_revision_comment TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS done_at TIMESTAMP WITH TIME ZONE;
