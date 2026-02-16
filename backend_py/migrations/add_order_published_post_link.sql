-- Order: link to published post in channel (for buyer to open)
ALTER TABLE orders ADD COLUMN IF NOT EXISTS published_post_link VARCHAR(512);
