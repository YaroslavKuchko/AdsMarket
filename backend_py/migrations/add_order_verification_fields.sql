-- Order: message_id and verified_at for post verification (24h/48h)
ALTER TABLE orders ADD COLUMN IF NOT EXISTS published_channel_message_id INTEGER;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP WITH TIME ZONE;
