-- Create the database
CREATE DATABASE notification_api;

-- Connect to the database
\c notification_api;

-- Install necessary extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create the tables
CREATE TABLE IF NOT EXISTS auth_type (
    name VARCHAR PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    email_address VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    _password VARCHAR,
    mobile_number VARCHAR,
    password_changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    logged_in_at TIMESTAMP,
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    state VARCHAR NOT NULL DEFAULT 'pending',
    platform_admin BOOLEAN NOT NULL DEFAULT FALSE,
    current_session_id UUID,
    auth_type VARCHAR REFERENCES auth_type(name) DEFAULT 'email_auth',
    blocked BOOLEAN NOT NULL DEFAULT FALSE,
    additional_information JSONB,
    identity_provider_user_id VARCHAR UNIQUE
);

CREATE TABLE IF NOT EXISTS branding_type (
    name VARCHAR(255) PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS email_branding (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    colour VARCHAR(7),
    logo VARCHAR(255),
    name VARCHAR(255) UNIQUE NOT NULL,
    text VARCHAR(255),
    brand_type VARCHAR(255) REFERENCES branding_type(name) NOT NULL DEFAULT 'org'
);

CREATE TABLE IF NOT EXISTS organisation_types (
    name VARCHAR(255) PRIMARY KEY,
    is_crown BOOLEAN,
    annual_free_sms_fragment_limit BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS organisation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    agreement_signed BOOLEAN,
    agreement_signed_at TIMESTAMP,
    agreement_signed_by_id UUID REFERENCES users(id),
    agreement_signed_on_behalf_of_name VARCHAR(255),
    agreement_signed_on_behalf_of_email_address VARCHAR(255),
    agreement_signed_version FLOAT,
    crown BOOLEAN,
    organisation_type VARCHAR(255) REFERENCES organisation_types(name),
    request_to_go_live_notes TEXT,
    email_branding_id UUID REFERENCES email_branding(id)
);

CREATE TABLE IF NOT EXISTS domain (
    domain VARCHAR(255) PRIMARY KEY,
    organisation_id UUID REFERENCES organisation(id) NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    display_name VARCHAR NOT NULL,
    identifier VARCHAR NOT NULL,
    priority INTEGER NOT NULL,
    load_balancing_weight INTEGER,
    notification_type VARCHAR(255) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by_id UUID REFERENCES users(id),
    supports_international BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS services (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    message_limit BIGINT NOT NULL,
    restricted BOOLEAN NOT NULL,
    research_mode BOOLEAN NOT NULL DEFAULT FALSE,
    email_from TEXT,
    created_by_id UUID REFERENCES users(id) NOT NULL,
    prefix_sms BOOLEAN NOT NULL DEFAULT FALSE,
    organisation_type VARCHAR(255) REFERENCES organisation_types(name),
    crown BOOLEAN,
    rate_limit INTEGER NOT NULL DEFAULT 3000,
    contact_link VARCHAR(255),
    volume_sms INTEGER,
    volume_email INTEGER,
    volume_letter INTEGER,
    consent_to_research BOOLEAN,
    count_as_live BOOLEAN NOT NULL DEFAULT TRUE,
    go_live_user_id UUID REFERENCES users(id),
    go_live_at TIMESTAMP,
    sending_domain VARCHAR(255),
    smtp_user VARCHAR(255),
    email_provider_id UUID REFERENCES provider_details(id),
    sms_provider_id UUID REFERENCES provider_details(id),
    organisation_id UUID REFERENCES organisation(id),
    p2p_enabled BOOLEAN DEFAULT FALSE
);

-- Create the inbound_numbers table
CREATE TABLE IF NOT EXISTS inbound_numbers (
    id UUID PRIMARY KEY,
    number VARCHAR(12) UNIQUE NOT NULL,
    provider VARCHAR NOT NULL,
    service_id UUID REFERENCES services(id),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    url_endpoint VARCHAR,
    self_managed BOOLEAN NOT NULL DEFAULT FALSE,
    auth_parameter VARCHAR
);

CREATE TABLE IF NOT EXISTS service_sms_senders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description VARCHAR(256),
    inbound_number_id UUID REFERENCES inbound_numbers(id) UNIQUE,
    is_default BOOLEAN NOT NULL DEFAULT TRUE,
    provider_id UUID REFERENCES provider_details(id),
    rate_limit INTEGER,
    rate_limit_interval INTEGER,
    service_id UUID REFERENCES services(id) NOT NULL,
    sms_sender VARCHAR(12) NOT NULL,
    sms_sender_specifics JSON,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS service_email_branding (
    service_id UUID REFERENCES services(id) PRIMARY KEY NOT NULL,
    email_branding_id UUID REFERENCES email_branding(id) NOT NULL
);

CREATE TABLE IF NOT EXISTS service_permission_types (
    name VARCHAR(255) PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS service_permissions (
    service_id UUID REFERENCES services(id) PRIMARY KEY NOT NULL,
    permission VARCHAR(255) REFERENCES service_permission_types(name) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS service_whitelist (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_id UUID REFERENCES services(id) NOT NULL,
    recipient_type VARCHAR(255) NOT NULL,
    recipient VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS service_callback_type (
    name VARCHAR PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS service_callback_channel (
    channel VARCHAR PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS service_callback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_id UUID REFERENCES services(id) NOT NULL,
    url VARCHAR NOT NULL,
    callback_type VARCHAR REFERENCES service_callback_type(name),
    bearer_token VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    updated_by_id UUID REFERENCES users(id) NOT NULL,
    notification_statuses JSONB,
    callback_channel VARCHAR REFERENCES service_callback_channel(channel) NOT NULL,
    include_provider_payload BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS key_types (
    name VARCHAR(255) PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    secret VARCHAR(255) UNIQUE NOT NULL,
    service_id UUID REFERENCES services(id) NOT NULL,
    key_type VARCHAR(255) REFERENCES key_types(name) NOT NULL,
    expiry_date TIMESTAMP,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    created_by_id UUID REFERENCES users(id) NOT NULL
);

CREATE TABLE IF NOT EXISTS communication_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    default_send_indicator BOOLEAN NOT NULL DEFAULT TRUE,
    name VARCHAR(255) NOT NULL UNIQUE,
    va_profile_item_id INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS template_process_type (
    name VARCHAR(255) PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS service_letter_contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_id UUID REFERENCES services(id) NOT NULL,
    contact_block TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT TRUE,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    template_type VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    content TEXT NOT NULL,
    content_as_html TEXT,
    content_as_plain_text TEXT,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    hidden BOOLEAN NOT NULL DEFAULT FALSE,
    onsite_notification BOOLEAN NOT NULL DEFAULT FALSE,
    subject TEXT,
    postage VARCHAR,
    reply_to_email VARCHAR(254),
    provider_id UUID REFERENCES provider_details(id),
    communication_item_id UUID REFERENCES communication_items(id),
    service_id UUID REFERENCES services(id) NOT NULL,
    created_by_id UUID REFERENCES users(id) NOT NULL,
    process_type VARCHAR(255) REFERENCES template_process_type(name) NOT NULL DEFAULT 'normal',
    service_letter_contact_id UUID REFERENCES service_letter_contacts(id)
);

CREATE TABLE IF NOT EXISTS template_redacted (
    template_id UUID REFERENCES templates(id) PRIMARY KEY NOT NULL,
    redact_personalisation BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by_id UUID REFERENCES users(id) NOT NULL
);

CREATE TABLE IF NOT EXISTS templates_history (
    id UUID REFERENCES templates(id) PRIMARY KEY NOT NULL,
    version INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    template_type VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    content TEXT NOT NULL,
    content_as_html TEXT,
    content_as_plain_text TEXT,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    hidden BOOLEAN NOT NULL DEFAULT FALSE,
    onsite_notification BOOLEAN NOT NULL DEFAULT FALSE,
    subject TEXT,
    postage VARCHAR,
    reply_to_email VARCHAR(254),
    provider_id UUID REFERENCES provider_details(id),
    communication_item_id UUID REFERENCES communication_items(id),
    service_id UUID REFERENCES services(id) NOT NULL,
    created_by_id UUID REFERENCES users(id) NOT NULL,
    process_type VARCHAR(255) REFERENCES template_process_type(name) NOT NULL DEFAULT 'normal',
    service_letter_contact_id UUID REFERENCES service_letter_contacts(id)
);

CREATE TABLE IF NOT EXISTS promoted_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_id UUID REFERENCES services(id) NOT NULL,
    template_id UUID REFERENCES templates(id) NOT NULL,
    promoted_service_id UUID,
    promoted_template_id UUID,
    promoted_template_content_digest TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    expected_cadence TEXT
);

CREATE TABLE IF NOT EXISTS provider_rates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    valid_from TIMESTAMP NOT NULL,
    rate NUMERIC NOT NULL,
    provider_id UUID REFERENCES provider_details(id) NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_details_history (
    id UUID PRIMARY KEY NOT NULL,
    display_name VARCHAR NOT NULL,
    identifier VARCHAR NOT NULL,
    priority INTEGER NOT NULL,
    load_balancing_weight INTEGER,
    notification_type VARCHAR(255) NOT NULL,
    active BOOLEAN NOT NULL,
    version INTEGER NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by_id UUID REFERENCES users(id),
    supports_international BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS job_status (
    name VARCHAR(255) PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    original_file_name VARCHAR NOT NULL,
    service_id UUID REFERENCES services(id) NOT NULL,
    template_id UUID REFERENCES templates(id),
    template_version INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    notification_count INTEGER NOT NULL,
    notifications_sent INTEGER NOT NULL DEFAULT 0,
    notifications_delivered INTEGER NOT NULL DEFAULT 0,
    notifications_failed INTEGER NOT NULL DEFAULT 0,
    processing_started TIMESTAMP,
    processing_finished TIMESTAMP,
    created_by_id UUID REFERENCES users(id),
    scheduled_for TIMESTAMP,
    job_status VARCHAR(255) REFERENCES job_status(name) NOT NULL DEFAULT 'pending',
    archived BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS verify_codes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) NOT NULL,
    code VARCHAR NOT NULL,
    code_type VARCHAR(255) NOT NULL,
    expiry_datetime TIMESTAMP NOT NULL,
    code_used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notification_status_types (
    name VARCHAR PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "to" VARCHAR,
    normalised_to VARCHAR,
    job_id UUID REFERENCES jobs(id),
    job_row_number INTEGER,
    service_id UUID REFERENCES services(id) NOT NULL,
    template_id UUID NOT NULL,
    template_version INTEGER NOT NULL,
    api_key_id UUID REFERENCES api_keys(id),
    key_type VARCHAR(255) REFERENCES key_types(name) NOT NULL,
    billable_units INTEGER NOT NULL DEFAULT 0,
    notification_type VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    sent_at TIMESTAMP,
    sent_by VARCHAR,
    updated_at TIMESTAMP,
    status VARCHAR REFERENCES notification_status_types(name) NOT NULL DEFAULT 'created',
    reference VARCHAR,
    client_reference VARCHAR,
    personalisation VARCHAR,
    international BOOLEAN NOT NULL DEFAULT FALSE,
    phone_prefix VARCHAR,
    rate_multiplier FLOAT,
    created_by_id UUID REFERENCES users(id),
    sms_sender_id UUID REFERENCES service_sms_senders(id),
    reply_to_text VARCHAR,
    status_reason VARCHAR,
    segments_count INTEGER NOT NULL DEFAULT 0,
    cost_in_millicents FLOAT NOT NULL DEFAULT 0,
    postage VARCHAR,
    billing_code VARCHAR(256),
    callback_url VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS notification_history (
    id UUID PRIMARY KEY NOT NULL,
    job_id UUID REFERENCES jobs(id),
    job_row_number INTEGER,
    service_id UUID REFERENCES services(id) NOT NULL,
    template_id UUID NOT NULL,
    template_version INTEGER NOT NULL,
    api_key_id UUID REFERENCES api_keys(id),
    key_type VARCHAR(255) REFERENCES key_types(name) NOT NULL,
    billable_units INTEGER NOT NULL DEFAULT 0,
    notification_type VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    sent_at TIMESTAMP,
    sent_by VARCHAR,
    updated_at TIMESTAMP,
    status VARCHAR REFERENCES notification_status_types(name) NOT NULL DEFAULT 'created',
    reference VARCHAR,
    client_reference VARCHAR,
    international BOOLEAN NOT NULL DEFAULT FALSE,
    phone_prefix VARCHAR,
    rate_multiplier FLOAT,
    created_by_id UUID REFERENCES users(id),
    sms_sender_id UUID REFERENCES service_sms_senders(id),
    segments_count INTEGER NOT NULL DEFAULT 0,
    cost_in_millicents FLOAT NOT NULL DEFAULT 0,
    postage VARCHAR,
    status_reason VARCHAR,
    billing_code VARCHAR(256)
);

CREATE TABLE IF NOT EXISTS scheduled_notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    notification_id UUID REFERENCES notifications(id) NOT NULL,
    scheduled_for TIMESTAMP NOT NULL,
    pending BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS recipient_identifiers (
    notification_id UUID REFERENCES notifications(id) PRIMARY KEY NOT NULL,
    id_type VARCHAR(255) NOT NULL,
    id_value VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS invite_status_type (
    name VARCHAR PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS invited_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_address VARCHAR(255) NOT NULL,
    user_id UUID REFERENCES users(id) NOT NULL,
    service_id UUID REFERENCES services(id) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR REFERENCES invite_status_type(name) NOT NULL DEFAULT 'pending',
    permissions VARCHAR NOT NULL,
    auth_type VARCHAR REFERENCES auth_type(name) NOT NULL DEFAULT 'email',
    folder_permissions JSONB NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS invited_organisation_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_address VARCHAR(255) NOT NULL,
    invited_by_id UUID REFERENCES users(id) NOT NULL,
    organisation_id UUID REFERENCES organisation(id) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR REFERENCES invite_status_type(name) NOT NULL DEFAULT 'pending'
);

-- Create the permission_types table
CREATE TABLE IF NOT EXISTS permission_types (
    name VARCHAR(255) PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_id UUID REFERENCES services(id),
    user_id UUID REFERENCES users(id) NOT NULL,
    permission VARCHAR(255) REFERENCES permission_types(name) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data JSON NOT NULL
);

CREATE TABLE IF NOT EXISTS rates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    valid_from TIMESTAMP NOT NULL,
    rate FLOAT NOT NULL,
    notification_type VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS inbound_sms (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    service_id UUID REFERENCES services(id) NOT NULL,
    notify_number VARCHAR NOT NULL,
    user_number VARCHAR NOT NULL,
    provider_date TIMESTAMP,
    provider_reference VARCHAR,
    provider VARCHAR NOT NULL,
    content VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS letter_rates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP,
    sheet_count INTEGER NOT NULL,
    rate NUMERIC NOT NULL,
    crown BOOLEAN NOT NULL,
    post_class VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_sorted_letter (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    billing_day DATE NOT NULL,
    file_name VARCHAR,
    unsorted_count INTEGER NOT NULL DEFAULT 0,
    sorted_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ft_billing (
    bst_date DATE NOT NULL,
    template_id UUID NOT NULL,
    service_id UUID NOT NULL,
    notification_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    rate_multiplier INTEGER NOT NULL,
    international BOOLEAN NOT NULL,
    rate NUMERIC NOT NULL,
    postage VARCHAR NOT NULL,
    billable_units INTEGER,
    notifications_sent INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    PRIMARY KEY (bst_date, template_id, service_id, notification_type, provider, rate_multiplier, international, rate, postage)
);

CREATE TABLE IF NOT EXISTS dm_datetime (
    bst_date DATE NOT NULL PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name TEXT NOT NULL,
    day INTEGER NOT NULL,
    bst_day INTEGER NOT NULL,
    day_of_year INTEGER NOT NULL,
    week_day_name TEXT NOT NULL,
    calendar_week INTEGER NOT NULL,
    quartal TEXT NOT NULL,
    year_quartal TEXT NOT NULL,
    year_month TEXT NOT NULL,
    year_calendar_week TEXT NOT NULL,
    financial_year INTEGER NOT NULL,
    utc_daytime_start TIMESTAMP NOT NULL,
    utc_daytime_end TIMESTAMP NOT NULL
);

CREATE INDEX ix_dm_datetime_yearmonth ON dm_datetime (year, month);

CREATE TABLE IF NOT EXISTS ft_notification_status (
    bst_date DATE NOT NULL DEFAULT CURRENT_DATE,
    template_id UUID NOT NULL DEFAULT uuid_generate_v4(),
    service_id UUID NOT NULL DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL DEFAULT uuid_generate_v4(),
    notification_type TEXT NOT NULL DEFAULT 'sms',
    key_type TEXT NOT NULL DEFAULT 'normal',
    notification_status TEXT NOT NULL DEFAULT 'created',
    status_reason TEXT NOT NULL DEFAULT '',
    notification_count INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    PRIMARY KEY (bst_date, template_id, service_id, job_id, notification_type, key_type, notification_status)
);

CREATE TABLE IF NOT EXISTS complaints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    notification_id UUID REFERENCES notification_history(id) NOT NULL,
    service_id UUID REFERENCES services(id) NOT NULL,
    feedback_id TEXT,
    complaint_type TEXT DEFAULT 'unknown complaint type',
    complaint_date TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS service_data_retention (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_id UUID REFERENCES services(id) NOT NULL,
    notification_type VARCHAR(255) NOT NULL,
    days_of_retention INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fido2_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) NOT NULL,
    name VARCHAR NOT NULL,
    key TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fido2_sessions (
    user_id UUID REFERENCES users(id) PRIMARY KEY NOT NULL,
    session TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS login_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS va_profile_local_cache (
    id SERIAL PRIMARY KEY,
    allowed BOOLEAN NOT NULL,
    va_profile_id BIGINT NOT NULL,
    communication_item_id INTEGER NOT NULL,
    communication_channel_id INTEGER NOT NULL,
    source_datetime TIMESTAMP NOT NULL,
    participant_id BIGINT,
    has_duplicate_mappings BOOLEAN NOT NULL DEFAULT FALSE,
    notification_id UUID,
    UNIQUE (va_profile_id, communication_item_id, communication_channel_id)
);

CREATE TABLE IF NOT EXISTS user_service_roles (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    role VARCHAR(255) NOT NULL,
    service_id UUID NOT NULL REFERENCES services(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notification_failures (
    notification_id UUID PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    body JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS template_folder (
    id UUID PRIMARY KEY,
    service_id UUID NOT NULL REFERENCES services(id),
    name VARCHAR NOT NULL,
    parent_id UUID REFERENCES template_folder(id)
);

-- Insert sample data
-- This first section is all the tables that lack ID fields
--------------------------------------------------------------------------------------------------------------------

-- Insert into auth_type table
INSERT INTO auth_type (name) VALUES
    ('email_auth'),
    ('sms_auth'),
    ('email'),
    ('sms');

-- Insert sample data into the service_permission_types table
INSERT INTO service_permission_types (name) VALUES
    ('email'),
    ('sms'),
    ('example_permission_type');

-- Insert sample data into the service_callback_type table
INSERT INTO service_callback_type (name) VALUES
    ('delivery_status'),
    ('complaint');

-- Insert sample data into the service_callback_channel table
INSERT INTO service_callback_channel (channel) VALUES
    ('webhook'),
    ('queue');

-- Insert sample data into the key_types table
INSERT INTO key_types (name) VALUES
    ('normal'),
    ('team'),
    ('test');

-- Insert sample data into the template_process_type table
INSERT INTO template_process_type (name) VALUES
    ('normal'),
    ('priority');

-- Insert sample data into the job_status table
INSERT INTO job_status (name) VALUES
    ('pending'),
    ('in progress'),
    ('completed'),
    ('failed');

-- Insert sample data into the permission_types table
INSERT INTO permission_types (name) VALUES
    ('send_emails'),
    ('send_texts'),
    ('manage_templates'),
    ('manage_service'),
    ('manage_api_keys');

-- Insert into branding_type
INSERT INTO branding_type (name) VALUES ('example_branding_type');

-- Insert into notification_status_types
INSERT INTO notification_status_types (name) VALUES
    ('created'),
    ('pending'),
    ('sending'),
    ('sent'),
    ('delivered'),
    ('failed'),
    ('temporary-failure'),
    ('permanent-failure');

-- Insert into organisation_types
INSERT INTO organisation_types (name, is_crown, annual_free_sms_fragment_limit) 
VALUES ('example_organisation_type', TRUE, 1000);

INSERT INTO invite_status_type (name) VALUES
    ('pending'),
    ('accepted'),
    ('cancelled');

-- Insert into all the tables that have IDs
--------------------------------------------------------------------------------------------------------------------

-- Insert sample data into the communication_items table
INSERT INTO communication_items (id, default_send_indicator, name, va_profile_item_id) VALUES
    ('00000000-0000-0000-0000-000000000001', TRUE, 'Sample Communication Item', 12345);

-- Insert sample data into the users table
INSERT INTO users (id, name, email_address, created_at, updated_at, _password, mobile_number, password_changed_at, logged_in_at, failed_login_count, state, platform_admin, current_session_id, auth_type, blocked, additional_information, identity_provider_user_id) VALUES
    ('00000000-0000-0000-0000-000000000001', 'John Doe', 'john.doe@example.com', CURRENT_TIMESTAMP, NULL, 'hashed_password', '1234567890', CURRENT_TIMESTAMP, NULL, 0, 'active', FALSE, NULL, 'email_auth', FALSE, '{}', 'github_id_123');

-- Insert into email_branding
INSERT INTO email_branding (id, colour, logo, name, text, brand_type) 
VALUES ('00000000-0000-0000-0000-000000000001', '#FFFFFF', 'logo.png', 'Example Branding', 'Example Text', 'example_branding_type');

-- Insert into organisation
INSERT INTO organisation (id, name, active, created_at, updated_at, agreement_signed, agreement_signed_at, agreement_signed_by_id, agreement_signed_on_behalf_of_name, agreement_signed_on_behalf_of_email_address, agreement_signed_version, crown, organisation_type, request_to_go_live_notes, email_branding_id) 
VALUES ('00000000-0000-0000-0000-000000000001', 'Example Organisation', TRUE, '2025-03-03 00:00:00', '2025-03-03 00:00:00', TRUE, '2025-03-03 00:00:00', '00000000-0000-0000-0000-000000000001', 'John Doe', 'john.doe@example.com', 1.0, TRUE, 'example_organisation_type', 'Request to go live notes', '00000000-0000-0000-0000-000000000001');

-- Insert into domain
INSERT INTO domain (domain, organisation_id) 
VALUES ('example.com', '00000000-0000-0000-0000-000000000001');

-- Insert into provider_details
INSERT INTO provider_details (id, display_name, identifier, priority, load_balancing_weight, notification_type, active, version, updated_at, created_by_id, supports_international) 
VALUES ('00000000-0000-0000-0000-000000000001', 'Example Provider', 'example_identifier', 1, 10, 'email', TRUE, 1, '2025-03-03 00:00:00', '00000000-0000-0000-0000-000000000001', TRUE);

-- Insert into provider_details_history
INSERT INTO provider_details_history (id, display_name, identifier, priority, load_balancing_weight, notification_type, active, version, updated_at, created_by_id, supports_international) 
VALUES ('00000000-0000-0000-0000-000000000001', 'Example Provider', 'example_identifier', 1, 10, 'email', TRUE, 1, '2025-03-03 00:00:00', '00000000-0000-0000-0000-000000000001', TRUE);

-- Insert into services
INSERT INTO services (id, name, created_at, updated_at, active, message_limit, restricted, research_mode, email_from, created_by_id, prefix_sms, organisation_type, crown, rate_limit, contact_link, volume_sms, volume_email, volume_letter, consent_to_research, count_as_live, go_live_user_id, go_live_at, sending_domain, smtp_user, email_provider_id, sms_provider_id, organisation_id, p2p_enabled) 
VALUES ('00000000-0000-0000-0000-000000000001', 'Example Service', '2025-03-03 00:00:00', '2025-03-03 00:00:00', TRUE, 1000, FALSE, FALSE, 'example@example.com', '00000000-0000-0000-0000-000000000001', FALSE, 'example_organisation_type', TRUE, 3000, 'http://example.com', 100, 100, 100, TRUE, TRUE, '00000000-0000-0000-0000-000000000001', '2025-03-03 00:00:00', 'example.com', 'smtp_user', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', TRUE);

-- Insert into service_email_branding
INSERT INTO service_email_branding (service_id, email_branding_id) 
VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001');

-- Insert sample data into the inbound_numbers table
INSERT INTO inbound_numbers (id, number, provider, service_id, active, created_at, updated_at, url_endpoint, self_managed, auth_parameter) VALUES
    ('00000000-0000-0000-0000-000000000001', '1234567890', 'Provider Name', '00000000-0000-0000-0000-000000000001', TRUE, CURRENT_TIMESTAMP, NULL, 'http://example.com', FALSE, 'auth_param');

-- Insert into service_whitelist
INSERT INTO service_whitelist (id, service_id, recipient_type, recipient, created_at) 
VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'email', 'whitelist@example.com', '2025-03-03 00:00:00');

-- Insert into service_callback
INSERT INTO service_callback (id, service_id, url, callback_type, bearer_token, created_at, updated_at, updated_by_id, notification_statuses, callback_channel, include_provider_payload) 
VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'http://callback.example.com', 'delivery_status', 'encrypted_token', '2025-03-03 00:00:00', '2025-03-03 00:00:00', '00000000-0000-0000-0000-000000000001', '{"status": "completed"}', 'webhook', TRUE);

-- Insert into api_keys
INSERT INTO api_keys (id, name, secret, service_id, key_type, expiry_date, revoked, created_at, updated_at, created_by_id) 
VALUES ('00000000-0000-0000-0000-000000000001', 'Example API Key', 'encrypted_secret', '00000000-0000-0000-0000-000000000001', 'normal', '2085-05-05 00:00:00', FALSE, '2025-01-01 00:00:00', '2025-03-03 00:00:00', '00000000-0000-0000-0000-000000000001');

-- Insert into template_folder
INSERT INTO template_folder (id, service_id, name, parent_id) 
VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'Example Folder', NULL);

-- Insert into templates
INSERT INTO templates (id, name, template_type, created_at, updated_at, content, content_as_html, content_as_plain_text, archived, hidden, onsite_notification, subject, postage, reply_to_email, provider_id, communication_item_id, service_id, created_by_id, process_type, service_letter_contact_id) 
VALUES ('00000000-0000-0000-0000-000000000001', 'Example Template', 'email', '2025-03-03 00:00:00', '2025-03-03 00:00:00', 'Example Content', 'Example Content as HTML', 'Example Content as Plain Text', FALSE, FALSE, FALSE, 'Example Subject', 'first', 'reply@example.com', '00000000-0000-0000-0000-000000000001', NULL, '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'normal', NULL);

-- Insert into template_redacted
INSERT INTO template_redacted (template_id, redact_personalisation, updated_at, updated_by_id) 
VALUES ('00000000-0000-0000-0000-000000000001', FALSE, '2025-03-03 00:00:00', '00000000-0000-0000-0000-000000000001');

-- Insert into templates_history
INSERT INTO templates_history (id, name, template_type, created_at, updated_at, content, content_as_html, content_as_plain_text, archived, hidden, onsite_notification, subject, postage, reply_to_email, provider_id, communication_item_id, service_id, created_by_id, process_type, service_letter_contact_id, version) 
VALUES ('00000000-0000-0000-0000-000000000001', 'Example Template', 'email', '2025-03-03 00:00:00', '2025-03-03 00:00:00', 'Example Content', 'Example Content as HTML', 'Example Content as Plain Text', FALSE, FALSE, FALSE, 'Example Subject', 'first', 'reply@example.com', '00000000-0000-0000-0000-000000000001', NULL, '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'normal', NULL, 1);

-- Insert into promoted_templates
INSERT INTO promoted_templates (id, service_id, template_id, promoted_service_id, promoted_template_id, promoted_template_content_digest, created_at, updated_at, expected_cadence) 
VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', NULL, NULL, 'digest', '2025-03-03 00:00:00', '2025-03-03 00:00:00', 'cadence');

-- Insert into provider_rates
INSERT INTO provider_rates (id, valid_from, rate, provider_id) 
VALUES ('00000000-0000-0000-0000-000000000001', '2025-03-03 00:00:00', 0.1, '00000000-0000-0000-0000-000000000001');

-- Insert into jobs
INSERT INTO jobs (id, original_file_name, service_id, template_id, template_version, created_at, updated_at, notification_count, notifications_sent, notifications_delivered, notifications_failed, processing_started, processing_finished, created_by_id, scheduled_for, job_status, archived) 
VALUES ('00000000-0000-0000-0000-000000000001', 'example_file.csv', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 1, '2025-03-03 00:00:00', '2025-03-03 00:00:00', 100, 50, 40, 10, '2025-03-03 00:00:00', '2025-03-03 00:00:00', '00000000-0000-0000-0000-000000000001', '2025-03-03 00:00:00', 'pending', FALSE);

-- Insert into verify_codes
INSERT INTO verify_codes (id, user_id, code, code_type, expiry_datetime, code_used, created_at) 
VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'hashed_code', 'email', '2035-03-03 00:00:00', FALSE, '2025-03-03 00:00:00');

-- Insert sample data into the service_sms_senders table
INSERT INTO service_sms_senders (id, archived, created_at, description, inbound_number_id, is_default, provider_id, rate_limit, rate_limit_interval, service_id, sms_sender, sms_sender_specifics, updated_at)
VALUES ('00000000-0000-0000-0000-000000000001', FALSE, CURRENT_TIMESTAMP, 'Sample SMS Sender', NULL, TRUE, '00000000-0000-0000-0000-000000000001', 100, 60, '00000000-0000-0000-0000-000000000001', '1234567890', '{"sender": "123456"}', NULL);

-- Insert into notifications
INSERT INTO notifications (id, "to", normalised_to, job_id, job_row_number, service_id, template_id, template_version, api_key_id, key_type, billable_units, notification_type, created_at, sent_at, sent_by, updated_at, status, reference, client_reference, personalisation, international, phone_prefix, rate_multiplier, created_by_id, sms_sender_id, reply_to_text, status_reason, segments_count, cost_in_millicents, postage, billing_code, callback_url) 
VALUES ('00000000-0000-0000-0000-000000000001', 'recipient@example.com', 'recipient@example.com', '00000000-0000-0000-0000-000000000001', 1, '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 1, '00000000-0000-0000-0000-000000000001', 'normal', 1, 'email', '2025-03-03 00:00:00', '2025-03-03 00:00:00', 'sender', '2025-03-03 00:00:00', 'created', 'reference', 'client_reference', 'encrypted_personalisation', FALSE, '1', 1.0, '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'reply_to_text', 'status_reason', 1, 0.1, 'first', 'billing_code', 'http://callback.example.com');

-- Insert into notification_history
INSERT INTO notification_history (id, job_id, job_row_number, service_id, template_id, template_version, api_key_id, key_type, billable_units, notification_type, created_at, sent_at, sent_by, updated_at, status, reference, client_reference, international, phone_prefix, rate_multiplier, created_by_id, sms_sender_id, segments_count, cost_in_millicents, postage, status_reason, billing_code) 
VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 1, '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 1, '00000000-0000-0000-0000-000000000001', 'normal', 1, 'email', '2025-03-03 00:00:00', '2025-03-03 00:00:00', 'sender', '2025-03-03 00:00:00', 'created', 'reference', 'client_reference', FALSE, '1', 1.0, '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 1, 0.1, 'first', 'status_reason', 'billing_code');

-- Insert into scheduled_notifications
INSERT INTO scheduled_notifications (id, notification_id, scheduled_for, pending) 
VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', '2025-03-03 00:00:00', TRUE);

-- Insert into recipient_identifiers
INSERT INTO recipient_identifiers (notification_id, id_type, id_value) 
VALUES ('00000000-0000-0000-0000-000000000001', 'VA_PROFILE_ID', 'id_value');

-- Insert into invited_users
INSERT INTO invited_users (id, email_address, user_id, service_id, created_at, status, permissions, auth_type, folder_permissions) 
VALUES ('00000000-0000-0000-0000-000000000001', 'invitee@example.com', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', '2025-03-03 00:00:00', 'pending', 'permission1,permission2', 'email', '[]');

-- Insert into invited_organisation_users
INSERT INTO invited_organisation_users (id, email_address, invited_by_id, organisation_id, created_at, status) 
VALUES ('00000000-0000-0000-0000-000000000001', 'invitee@example.com', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', '2025-03-03 00:00:00', 'pending');

-- Insert into permissions
INSERT INTO permissions (id, service_id, user_id, permission, created_at) 
VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'send_emails', '2025-03-03 00:00:00');

-- Insert into events
INSERT INTO events (id, event_type, created_at, data) 
VALUES ('00000000-0000-0000-0000-000000000001', 'event_type', '2025-03-03 00:00:00', '{"key": "value"}');

-- Insert into service_permission
INSERT INTO service_permissions (service_id, permission, created_at) 
VALUES ('00000000-0000-0000-0000-000000000001', 'email', '2025-03-03 00:00:00');
