-- Order: secret post_token for /start post_{token} links
ALTER TABLE orders ADD COLUMN IF NOT EXISTS post_token VARCHAR(16);
CREATE UNIQUE INDEX IF NOT EXISTS ix_orders_post_token ON orders (post_token) WHERE post_token IS NOT NULL;
