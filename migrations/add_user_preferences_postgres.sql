-- Migration: Add user preferences columns to users table
-- Run this on PostgreSQL (Render)

-- Check if avatar_url exists before adding
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'avatar_url') THEN
        ALTER TABLE users ADD COLUMN avatar_url VARCHAR(255);
        RAISE NOTICE 'Added column: avatar_url';
    ELSE
        RAISE NOTICE 'Skipped (exists): avatar_url';
    END IF;
END$$;

-- Add timezone
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'timezone') THEN
        ALTER TABLE users ADD COLUMN timezone VARCHAR(100) DEFAULT 'auto';
        RAISE NOTICE 'Added column: timezone';
    ELSE
        RAISE NOTICE 'Skipped (exists): timezone';
    END IF;
END$$;

-- Add date_format
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'date_format') THEN
        ALTER TABLE users ADD COLUMN date_format VARCHAR(20) DEFAULT 'DD/MM/YYYY';
        RAISE NOTICE 'Added column: date_format';
    ELSE
        RAISE NOTICE 'Skipped (exists): date_format';
    END IF;
END$$;

-- Add language
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'language') THEN
        ALTER TABLE users ADD COLUMN language VARCHAR(10) DEFAULT 'tr';
        RAISE NOTICE 'Added column: language';
    ELSE
        RAISE NOTICE 'Skipped (exists): language';
    END IF;
END$$;

-- Add currency
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'currency') THEN
        ALTER TABLE users ADD COLUMN currency VARCHAR(10) DEFAULT 'TRY';
        RAISE NOTICE 'Added column: currency';
    ELSE
        RAISE NOTICE 'Skipped (exists): currency';
    END IF;
END$$;

-- Add pref_activity_after_win
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'pref_activity_after_win') THEN
        ALTER TABLE users ADD COLUMN pref_activity_after_win BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added column: pref_activity_after_win';
    ELSE
        RAISE NOTICE 'Skipped (exists): pref_activity_after_win';
    END IF;
END$$;

-- Add pref_detail_deal
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'pref_detail_deal') THEN
        ALTER TABLE users ADD COLUMN pref_detail_deal BOOLEAN DEFAULT TRUE;
        RAISE NOTICE 'Added column: pref_detail_deal';
    ELSE
        RAISE NOTICE 'Skipped (exists): pref_detail_deal';
    END IF;
END$$;

-- Add pref_detail_contact
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'pref_detail_contact') THEN
        ALTER TABLE users ADD COLUMN pref_detail_contact BOOLEAN DEFAULT TRUE;
        RAISE NOTICE 'Added column: pref_detail_contact';
    ELSE
        RAISE NOTICE 'Skipped (exists): pref_detail_contact';
    END IF;
END$$;

-- Add pref_detail_org
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'pref_detail_org') THEN
        ALTER TABLE users ADD COLUMN pref_detail_org BOOLEAN DEFAULT TRUE;
        RAISE NOTICE 'Added column: pref_detail_org';
    ELSE
        RAISE NOTICE 'Skipped (exists): pref_detail_org';
    END IF;
END$$;

-- Add pref_us_phone
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'pref_us_phone') THEN
        ALTER TABLE users ADD COLUMN pref_us_phone BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added column: pref_us_phone';
    ELSE
        RAISE NOTICE 'Skipped (exists): pref_us_phone';
    END IF;
END$$;

-- Add pref_email_new_tab
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'pref_email_new_tab') THEN
        ALTER TABLE users ADD COLUMN pref_email_new_tab BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added column: pref_email_new_tab';
    ELSE
        RAISE NOTICE 'Skipped (exists): pref_email_new_tab';
    END IF;
END$$;

-- Add pref_win_celebration
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'pref_win_celebration') THEN
        ALTER TABLE users ADD COLUMN pref_win_celebration BOOLEAN DEFAULT TRUE;
        RAISE NOTICE 'Added column: pref_win_celebration';
    ELSE
        RAISE NOTICE 'Skipped (exists): pref_win_celebration';
    END IF;
END$$;

-- Add pref_auto_labels
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'pref_auto_labels') THEN
        ALTER TABLE users ADD COLUMN pref_auto_labels BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added column: pref_auto_labels';
    ELSE
        RAISE NOTICE 'Skipped (exists): pref_auto_labels';
    END IF;
END$$;
