from app import app, db

with app.app_context():
    # Check if tags table exists
    result = db.session.execute(db.text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('tags', 'contact_tags')"
    )).fetchall()
    
    print("Existing tables:", [r[0] for r in result])
    
    if not result:
        print("\n❌ tags and contact_tags tables are MISSING!")
        print("Running db.create_all() to create them...")
        db.create_all()
        print("✓ Tables created")
        
        # Verify
        result = db.session.execute(db.text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('tags', 'contact_tags')"
        )).fetchall()
        print("After create_all():", [r[0] for r in result])
