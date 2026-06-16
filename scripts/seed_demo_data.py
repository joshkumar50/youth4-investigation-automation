#!/usr/bin/env python3
"""
Demo Data Seeder — Operation Nightfall
Seeds the database with a complete pre-built investigation case for hackathon demo.
Run: python scripts/seed_demo_data.py
"""
import os
import sys
import uuid
import json
import asyncio
import random
from datetime import datetime, timezone, timedelta

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://iip_user:iip_secret_2024@localhost:5432/investigation_db"
).replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def seed():
    from sqlalchemy import create_engine, text
    engine = create_engine(DATABASE_URL)

    print("🔧 Investigation Intelligence Platform — Demo Data Seeder")
    print("=" * 60)

    with engine.connect() as conn:
        # ── 1. Demo User ──────────────────────────────────────────
        print("Creating demo user...")
        # bcrypt hash of "Demo1234!" — pre-computed for speed
        hashed_pw = "$2b$12$p2CYqQfsYMWW9yFEG1190.41ib8v9mD0NtqUGk9LthEM1EMDgd5uS"
        demo_user_id = str(uuid.uuid4())
        conn.execute(text("""
            INSERT INTO users (id, email, hashed_password, full_name, role, is_active, created_at, updated_at)
            VALUES (:id, 'demo@iip.gov', :pw, 'Det. Sarah Connor', 'INVESTIGATOR', true, now(), now())
            ON CONFLICT (email) DO UPDATE SET hashed_password = :pw
            RETURNING id
        """), {"id": demo_user_id, "pw": hashed_pw})

        # Get actual user id
        result = conn.execute(text("SELECT id FROM users WHERE email = 'demo@iip.gov'"))
        demo_user_id = str(result.scalar_one())
        print(f"  ✓ Demo user: demo@iip.gov / Demo1234!")

        # ── 2. Demo Case ──────────────────────────────────────────
        print("Creating demo case: Operation Nightfall...")
        case_id = str(uuid.uuid4())
        conn.execute(text("""
            INSERT INTO cases (id, title, description, case_number, status, priority, tags, created_by, created_at, updated_at)
            VALUES (
                :id,
                'Operation Nightfall',
                'Multi-jurisdictional investigation into suspected financial crime network operating through encrypted communications and shell companies. Digital evidence collected from 4 suspects over 6-month surveillance operation.',
                'CASE-2024-NF001',
                'ACTIVE',
                'CRITICAL',
                '["financial-crime", "digital-forensics", "organized-crime", "cybercrime"]'::jsonb,
                :user_id,
                :created_at,
                now()
            )
            ON CONFLICT DO NOTHING
            RETURNING id
        """), {
            "id": case_id,
            "user_id": demo_user_id,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=14)).isoformat(),
        })

        # Check if case was inserted or get existing
        result = conn.execute(text("SELECT id FROM cases WHERE case_number = 'CASE-2024-NF001'"))
        row = result.fetchone()
        if row:
            case_id = str(row[0])
        print(f"  ✓ Case ID: {case_id}")

        # ── 3. Evidence Files ─────────────────────────────────────
        print("Creating evidence records...")
        evidence_files = [
            ("financial_records_q1.pdf", "pdf", "financial", "completed", "critical", 0.92),
            ("suspect_a_phone_dump.pdf", "pdf", "communication", "completed", "high", 0.78),
            ("surveillance_photo_001.jpg", "image", "identity", "completed", "medium", 0.45),
            ("surveillance_photo_002.jpg", "image", "location", "completed", "medium", 0.38),
            ("whatsapp_export_group.json", "chat_export", "communication", "completed", "critical", 0.88),
            ("telegram_export_private.json", "chat_export", "communication", "completed", "high", 0.71),
            ("bank_statement_march.pdf", "pdf", "financial", "completed", "critical", 0.95),
            ("vehicle_registration.docx", "document", "identity", "completed", "medium", 0.42),
            ("cctv_footage_atm.mp4", "video", "media", "completed", "high", 0.65),
            ("seized_laptop_notes.txt", "document", "threat", "completed", "critical", 0.89),
            ("property_documents.pdf", "pdf", "legal", "completed", "medium", 0.33),
            ("crypto_wallet_transactions.csv", "document", "financial", "completed", "high", 0.77),
        ]

        evidence_ids = []
        for fname, ftype, category, status, threat, score in evidence_files:
            ev_id = str(uuid.uuid4())
            evidence_ids.append(ev_id)
            size = random.randint(50000, 5000000)
            created = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 13))
            conn.execute(text("""
                INSERT INTO evidence (
                    id, case_id, filename, original_filename, file_type, category,
                    category_confidence, storage_path, size_bytes, mime_type,
                    processing_status, threat_level, threat_score, uploaded_by,
                    created_at, processed_at, extracted_text, extraction_metadata
                ) VALUES (
                    :id, :case_id, :fname, :fname, :ftype, :category,
                    :conf, :path, :size, 'application/octet-stream',
                    :status, :threat, :score, :user_id,
                    :created_at, :processed_at, :text, CAST(:meta AS jsonb)
                ) ON CONFLICT DO NOTHING
            """), {
                "id": ev_id, "case_id": case_id,
                "fname": fname, "ftype": ftype.upper(), "category": category.upper(),
                "conf": round(random.uniform(0.75, 0.98), 2),
                "path": f"cases/{case_id}/{ev_id}_{fname}",
                "size": size, "status": status.upper(), "threat": threat.upper(), "score": score,
                "user_id": demo_user_id,
                "created_at": created.isoformat(),
                "processed_at": (created + timedelta(minutes=random.randint(2, 15))).isoformat(),
                "text": f"[Extracted text from {fname}] Financial transactions detected. Multiple entities identified.",
                "meta": json.dumps({"pages": random.randint(1, 20), "word_count": random.randint(100, 5000)}),
            })
        print(f"  ✓ {len(evidence_files)} evidence files created")

        # ── 4. Entities ───────────────────────────────────────────
        print("Creating extracted entities...")
        entities = [
            # Persons
            ("Marcus Chen", "marcus chen", "PERSON", 0.96, 8, 0.87, True),
            ("Elena Rodriguez", "elena rodriguez", "PERSON", 0.94, 6, 0.72, True),
            ("Viktor Petrov", "viktor petrov", "PERSON", 0.92, 4, 0.65, True),
            ("Amanda Walsh", "amanda walsh", "PERSON", 0.89, 3, 0.41, False),
            ("James Blackwood", "james blackwood", "PERSON", 0.87, 5, 0.78, True),
            # Organizations
            ("NightHawk Capital LLC", "nighthawk capital llc", "ORG", 0.95, 7, 0.83, True),
            ("Meridian Trading Ltd", "meridian trading ltd", "ORG", 0.91, 4, 0.71, True),
            ("First Pacific Bank", "first pacific bank", "ORG", 0.88, 5, 0.52, False),
            # Locations
            ("Dubai, UAE", "dubai, uae", "GPE", 0.93, 6, 0.68, True),
            ("Cayman Islands", "cayman islands", "GPE", 0.97, 8, 0.79, True),
            ("Singapore", "singapore", "GPE", 0.94, 4, 0.55, False),
            ("Nassau, Bahamas", "nassau, bahamas", "GPE", 0.91, 3, 0.61, True),
            # Communications
            ("+1-555-0192", "+1-555-0192", "PHONE", 0.99, 12, 0.88, True),
            ("+971-50-1234567", "+971-50-1234567", "PHONE", 0.99, 8, 0.76, True),
            ("mchen.secure@proton.me", "mchen.secure@proton.me", "EMAIL", 0.99, 9, 0.84, True),
            ("nighthawk.ops@tutanota.com", "nighthawk.ops@tutanota.com", "EMAIL", 0.99, 6, 0.77, True),
            # Financial
            ("$2,400,000", "$2,400,000", "MONEY", 0.98, 3, 0.82, True),
            ("$847,500", "$847,500", "MONEY", 0.98, 2, 0.71, False),
            # Dates
            ("March 15, 2024", "march 15, 2024", "DATE", 0.95, 5, 0.45, False),
            ("February 28, 2024", "february 28, 2024", "DATE", 0.93, 3, 0.38, False),
            # IDs
            ("NH-2024-7291", "nh-2024-7291", "ID_NUMBER", 0.97, 4, 0.69, True),
            # URLs
            ("https://nighthawkcap.offshore.io", "https://nighthawkcap.offshore.io", "URL", 0.99, 3, 0.75, True),
        ]

        entity_ids = {}
        for value, norm, etype, conf, freq, threat_rel, is_primary in entities:
            ent_id = str(uuid.uuid4())
            ev_id = random.choice(evidence_ids)
            entity_ids[norm] = ent_id
            
            # Map spaCy entity types to database Enum
            db_etype = "ORGANIZATION" if etype == "ORG" else "LOCATION" if etype == "GPE" else etype
            
            conn.execute(text("""
                INSERT INTO entities (
                    id, case_id, evidence_id, entity_type, value, normalized_value,
                    confidence, frequency, threat_relevance, is_primary, created_at
                ) VALUES (
                    :id, :case_id, :ev_id, :etype, :value, :norm,
                    :conf, :freq, :threat_rel, :is_primary, now()
                ) ON CONFLICT DO NOTHING
            """), {
                "id": ent_id, "case_id": case_id, "ev_id": ev_id,
                "etype": db_etype, "value": value, "norm": norm,
                "conf": conf, "freq": freq, "threat_rel": threat_rel,
                "is_primary": is_primary,
            })
        print(f"  ✓ {len(entities)} entities extracted")

        # ── 5. Relationships ──────────────────────────────────────
        print("Building entity relationship graph...")
        relationships = [
            ("marcus chen", "nighthawk capital llc", "PERSON", "ORG", "controls", 2.8),
            ("marcus chen", "elena rodriguez", "PERSON", "PERSON", "co_occurrence", 2.1),
            ("marcus chen", "+1-555-0192", "PERSON", "PHONE", "uses_contact", 1.9),
            ("marcus chen", "mchen.secure@proton.me", "PERSON", "EMAIL", "uses_contact", 2.2),
            ("marcus chen", "dubai, uae", "PERSON", "GPE", "located_in", 1.6),
            ("marcus chen", "cayman islands", "PERSON", "GPE", "located_in", 1.8),
            ("elena rodriguez", "meridian trading ltd", "PERSON", "ORG", "associated_with", 1.7),
            ("elena rodriguez", "+971-50-1234567", "PERSON", "PHONE", "uses_contact", 1.5),
            ("viktor petrov", "nighthawk capital llc", "PERSON", "ORG", "associated_with", 1.4),
            ("viktor petrov", "cayman islands", "PERSON", "GPE", "located_in", 1.3),
            ("nighthawk capital llc", "cayman islands", "ORG", "GPE", "registered_in", 2.5),
            ("nighthawk capital llc", "meridian trading ltd", "ORG", "ORG", "co_occurrence", 1.8),
            ("james blackwood", "first pacific bank", "PERSON", "ORG", "associated_with", 1.6),
            ("james blackwood", "nassau, bahamas", "PERSON", "GPE", "located_in", 1.4),
            ("nighthawk.ops@tutanota.com", "nighthawk capital llc", "EMAIL", "ORG", "associated_with", 2.0),
        ]

        for src_norm, tgt_norm, src_type, tgt_type, rel_type, weight in relationships:
            src_id = entity_ids.get(src_norm)
            tgt_id = entity_ids.get(tgt_norm)
            if not src_id or not tgt_id:
                continue
            conn.execute(text("""
                INSERT INTO entity_relationships (
                    id, case_id, source_entity_id, target_entity_id,
                    relationship_type, weight, evidence_count, created_at
                ) VALUES (
                    gen_random_uuid(), :case_id, :src, :tgt,
                    :rel_type, :weight, :ev_count, now()
                ) ON CONFLICT DO NOTHING
            """), {
                "case_id": case_id, "src": src_id, "tgt": tgt_id,
                "rel_type": rel_type, "weight": weight,
                "ev_count": random.randint(1, 5),
            })
        print(f"  ✓ {len(relationships)} entity relationships mapped")

        # ── 6. Timeline Events ────────────────────────────────────
        print("Reconstructing investigation timeline...")
        base_date = datetime.now(timezone.utc) - timedelta(days=180)
        timeline_events = [
            (base_date + timedelta(days=2), "FILE_CREATED", "Initial communication intercepted", "WhatsApp group created by Marcus Chen with 4 participants"),
            (base_date + timedelta(days=15), "COMMUNICATION_SENT", "Coordination meeting arranged", "Encrypted message: 'Cayman accounts ready. Proceed with phase 2.'"),
            (base_date + timedelta(days=28), "TRANSACTION", "Large financial transfer detected", "$847,500 wire transfer from First Pacific Bank to offshore account"),
            (base_date + timedelta(days=41), "LOCATION_VISIT", "Dubai connection established", "Viktor Petrov arrives Dubai — corroborated by CCTV metadata"),
            (base_date + timedelta(days=55), "COMMUNICATION_SENT", "Shell company referenced", "NightHawk Capital LLC mentioned across 3 evidence sources"),
            (base_date + timedelta(days=70), "TRANSACTION", "Second major transfer", "$2,400,000 routed through Meridian Trading Ltd"),
            (base_date + timedelta(days=84), "ENTITY_MENTION", "Cayman Islands account opened", "Legal document: offshore entity registration confirmed"),
            (base_date + timedelta(days=97), "COMMUNICATION_SENT", "Threat communication detected", "Seized laptop notes reference to 'silencing' witnesses"),
            (base_date + timedelta(days=112), "INCIDENT", "Digital evidence seized", "Laptop and mobile devices confiscated from Marcus Chen residence"),
            (base_date + timedelta(days=126), "FILE_CREATED", "Bank records subpoenaed", "First Pacific Bank customer records obtained via legal order"),
            (base_date + timedelta(days=140), "COMMUNICATION_RECEIVED", "Elena Rodriguez contact identified", "Proton Mail exchange between suspects confirmed"),
            (base_date + timedelta(days=155), "ENTITY_MENTION", "Nassau property link found", "James Blackwood linked to Bahamas property — document forensics"),
            (base_date + timedelta(days=168), "DOCUMENT_SIGNED", "Legal review initiated", "Case transferred to prosecution for review"),
            (base_date + timedelta(days=172), "FILE_CREATED", "Case file compiled", "Complete evidence package assembled for court submission"),
        ]

        for ts, etype, title, desc in timeline_events:
            ev_id = random.choice(evidence_ids) if random.random() > 0.3 else None
            conn.execute(text("""
                INSERT INTO timeline_events (
                    id, case_id, evidence_id, event_type, title, description,
                    event_timestamp, confidence, created_at
                ) VALUES (
                    gen_random_uuid(), :case_id, :ev_id, :etype, :title, :desc,
                    :ts, :conf, now()
                ) ON CONFLICT DO NOTHING
            """), {
                "case_id": case_id, "ev_id": ev_id, "etype": etype,
                "title": title, "desc": desc, "ts": ts.isoformat(),
                "conf": round(random.uniform(0.72, 0.97), 2),
            })
        print(f"  ✓ {len(timeline_events)} timeline events reconstructed")

        # ── 7. Investigation Notes ────────────────────────────────
        print("Generating AI investigation notes...")
        notes = [
            ("Operation Nightfall: Critical financial crime network involving 5 identified suspects across 4 jurisdictions. Marcus Chen identified as primary orchestrator. Network uses encrypted communications and shell companies to launder proceeds. Total traced amount: $3.2M+. Recommend immediate asset freeze.", "ai_summary"),
            ("Entity graph reveals hub-and-spoke structure with Marcus Chen at center. NightHawk Capital LLC serves as primary vehicle. Communication security measures (ProtonMail, Tutanota) indicate technical sophistication. Recommend deep-dive into cryptocurrency transaction records.", "ai_insight"),
            ("Timeline analysis shows 6-month operational pattern with major transfers on the 15th of each month. Dubai-Cayman corridor is primary money movement route. James Blackwood's Bahamas connection warrants separate investigation thread.", "ai_recommendation"),
        ]
        for content, note_type in notes:
            conn.execute(text("""
                INSERT INTO investigation_notes (
                    id, case_id, content, note_type, generated_by, created_at
                ) VALUES (
                    gen_random_uuid(), :case_id, :content, :note_type, 'AI Pipeline v1.0', now()
                )
            """), {"case_id": case_id, "content": content, "note_type": note_type})
        print(f"  ✓ {len(notes)} AI investigation notes generated")

        conn.commit()

    print()
    print("=" * 60)
    print("✅ Demo data seeded successfully!")
    print()
    print("📋 Demo Credentials:")
    print("   Email:    demo@iip.gov")
    print("   Password: Demo1234!")
    print()
    print("🔬 Demo Case: Operation Nightfall (CASE-2024-NF001)")
    print(f"   Evidence: 12 files | Entities: {len(entities)} | Timeline: {len(timeline_events)} events")
    print(f"   Relationships: {len(relationships)} | Status: CRITICAL / ACTIVE")
    print()
    print("🚀 Start the frontend: cd frontend && npm run dev")
    print("🔗 API Docs: http://localhost:8000/docs")


if __name__ == "__main__":
    try:
        seed()
    except Exception as e:
        print(f"\n❌ Seeding failed: {e}")
        print("\nMake sure PostgreSQL is running and tables are created:")
        print("  docker-compose up postgres -d")
        print("  cd backend && alembic upgrade head")
        raise
