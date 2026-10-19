-- One database per service. Services never reach into each other's data.
CREATE DATABASE ecom_users;
CREATE DATABASE ecom_publications;
CREATE DATABASE ecom_cart;
CREATE DATABASE ecom_orders;
CREATE DATABASE ecom_goods;

-- Gorse keeps its model data here; its cache lives in Redis.
CREATE DATABASE ecom_gorse;
