import os

from flask import Flask, render_template, jsonify, request
from sqlalchemy import desc

from database import SessionLocal
from models import BreathingRecord
from alarm_manager import process

# backend/app.py -> lùi 1 cấp để ra thư mục gốc
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "dashboard", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "dashboard", "static")

app = Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
    static_folder=STATIC_DIR,
)


def record_to_dict(record):
    return {
        "id": record.id,
        "bpm": record.bpm,
        "source": record.source,
        "note": record.note,
        "recorded_at": record.created_at.isoformat(),
    }


@app.route("/")
def dashboard():
    return render_template("index.html")


@app.route("/api/latest", methods=["GET"])
def get_latest():

    db = SessionLocal()

    try:
        record = (
            db.query(BreathingRecord)
            .order_by(desc(BreathingRecord.created_at))
            .first()
        )

        if record is None:
            return jsonify({"message": "Chưa có dữ liệu"}), 404

        return jsonify(record_to_dict(record)), 200

    finally:
        db.close()


@app.route("/api/history", methods=["GET"])
def get_history():

    limit = request.args.get("limit", default=100, type=int)

    db = SessionLocal()

    try:

        records = (
            db.query(BreathingRecord)
            .order_by(desc(BreathingRecord.created_at))
            .limit(limit)
            .all()
        )

        return jsonify([record_to_dict(r) for r in records]), 200

    finally:
        db.close()


@app.route("/api/breathing", methods=["POST"])
def ingest_breathing():

    data = request.get_json(silent=True)

    if not data or "bpm" not in data:
        return jsonify({"error": "Thiếu field bpm"}), 400

    try:
        bpm_value = float(data["bpm"])

    except (TypeError, ValueError):
        return jsonify({"error": "bpm phải là số"}), 400

    image_path = data.get("image")

    db = SessionLocal()

    try:

        record = BreathingRecord(
            bpm=bpm_value,
            source=data.get("source", "camera_ai"),
            note=data.get("note"),
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        # ===========================
        # Kiểm tra cảnh báo và gửi mail
        # ===========================

        from datetime import datetime

        print("=" * 60)
        print(f"[Backend] Nhận dữ liệu : {datetime.now():%Y-%m-%d %H:%M:%S}")
        print(f"[Backend] BPM          : {bpm_value:.2f}")
        print(f"[Backend] Image        : {data.get('image')}")
        print("=" * 60)
        process(
            bpm=bpm_value,
            image_path=data.get("image")
        )

        return jsonify(record_to_dict(record)), 201

    finally:
        db.close()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )