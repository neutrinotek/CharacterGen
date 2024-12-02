-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    is_active BOOLEAN NOT NULL DEFAULT 0,
    can_delete_files BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    reset_token VARCHAR(100) UNIQUE,
    reset_token_expiry TIMESTAMP
);

-- Login attempts table for security monitoring
CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    success BOOLEAN NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Model permissions table
CREATE TABLE IF NOT EXISTS model_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    model_type VARCHAR(20) NOT NULL,  -- 'checkpoint' or 'lora'
    model_name VARCHAR(255) NOT NULL,
    granted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    granted_by INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (granted_by) REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE(user_id, model_type, model_name)
);

-- Default permissions table (for new users)
CREATE TABLE IF NOT EXISTS default_model_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_type VARCHAR(20) NOT NULL,  -- 'checkpoint' or 'lora'
    model_name VARCHAR(255) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    UNIQUE(model_type, model_name)
);

-- Character permissions table
CREATE TABLE IF NOT EXISTS character_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    character_name VARCHAR(255) NOT NULL,
    can_generate BOOLEAN NOT NULL DEFAULT 1,
    can_browse BOOLEAN NOT NULL DEFAULT 1,
    granted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    granted_by INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (granted_by) REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE(user_id, character_name)
);

-- Default character permissions table (for new users)
CREATE TABLE IF NOT EXISTS default_character_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_name VARCHAR(255) NOT NULL,
    can_generate BOOLEAN NOT NULL DEFAULT 1,
    can_browse BOOLEAN NOT NULL DEFAULT 1,
    UNIQUE(character_name)
);

CREATE TABLE IF NOT EXISTS user_latest_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    prompt TEXT,
    image_path TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_login_attempts_username ON login_attempts(username);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip_address);
CREATE INDEX IF NOT EXISTS idx_model_permissions_user ON model_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_model_permissions_model ON model_permissions(model_type, model_name);
CREATE INDEX IF NOT EXISTS idx_character_permissions_user ON character_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_latest_content ON user_latest_content(user_id);