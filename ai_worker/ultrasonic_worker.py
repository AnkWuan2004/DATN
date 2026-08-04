"""
ultrasonic_worker.py
---------------------
Nhan du lieu khoang cach (cm) tu ESP8266+HC-SR04 qua HTTP,
xu ly bang CUNG pipeline voi ESP32-CAM:
    bandpass Butterworth 0.1-0.5 Hz -> find_peaks voi prominence
    -> tinh BPM -> POST /api/breathing (source="ultrasonic")

Chay doc lap song song voi breathing_worker.py (ESP32-CAM).
Ket qua hien thi song song tren dashboard de so sanh.

Cach chay:
    python ultrasonic_worker.py
    python ultrasonic_worker.py --api http://127.0.0.1:5000 --interval 60

Yeu cau: cung PYTHONPATH voi breathing_worker.py de dung lai cac
module ai/ (signal_filter.py, breathing_rate.py).

FIX: truoc day script bi loi "ModuleNotFoundError: No module named
'ai.signal_filter'" khi chay tu mot so IDE (PyCharm/Spyder di kem
Anaconda) hoac khi working directory luc chay khac voi thu muc chua
file nay. Nguyen nhan: Python chi tu dong them thu muc chua script
vao sys.path khi chay truc tiep bang `python file.py` tu terminal --
mot so cach chay khac (qua IDE, qua shortcut, qua tool khac) khong
dam bao dieu nay. Doan code ngay duoi day ep sys.path LUON co dung
thu muc chua file ultrasonic_worker.py, bat ke chay bang cach nao,
de dam bao `from ai.signal_filter import ...` luon tim duoc thu muc
ai/ nam CUNG CAP voi file nay.
"""

import os
import sys

# Luon dam bao thu muc chua file nay (vd D:\breathing-monitor\ai_worker)
# nam trong sys.path, de import "ai.signal_filter" / "ai.breathing_rate"
# hoat dong on dinh du chay bang cach nao (terminal, IDE, double-click).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import argparse
import time
from collections import deque

import matplotlib.pyplot as plt
import requests
from flask import Flask, request, jsonify

# Dung lai dung pipeline voi ESP32-CAM worker
try:
    from ai.signal_filter import SignalFilter
    from ai.breathing_rate import BreathingRateEstimator
except ModuleNotFoundError as e:
    # FIX: bao loi RO RANG va HUONG DAN cu the thay vi de traceback
    # kho hieu, giup phat hien nhanh neu thu muc ai/ thuc su chua ton
    # tai hoac dat sai vi tri (khong chi la van de sys.path).
    expected_ai_dir = os.path.join(_THIS_DIR, "ai")
    print(
        "[ultrasonic] LOI: khong import duoc module trong thu muc ai/.\n"
        f"    Da tim trong: {expected_ai_dir}\n"
        f"    Thu muc do co ton tai khong? {os.path.isdir(expected_ai_dir)}\n"
        "    Kiem tra: (1) thu muc 'ai' co nam CUNG CAP voi ultrasonic_worker.py "
        "khong (vd cung trong ai_worker/)? "
        "(2) file signal_filter.py va breathing_rate.py co nam trong do khong? "
        "(3) neu dung IDE, thu chay lai bang terminal: "
        "'cd ai_worker' roi 'python ultrasonic_worker.py' de loai tru van de "
        "working directory cua IDE."
    )
    raise


def parse_args():
    parser = argparse.ArgumentParser(description="Ultrasonic breathing worker")
    parser.add_argument(
        "--api", default="http://127.0.0.1:5000",
        help="Base URL cua Flask backend chinh (mac dinh http://127.0.0.1:5000)"
    )
    parser.add_argument(
        "--port", type=int, default=5002,
        help="Cong lang nghe nhan du lieu tu ESP8266 (mac dinh 5002)"
    )
    parser.add_argument(
        "--interval", type=float, default=60.0,
        help="Do dai khoi tin hieu (giay), mac dinh 60 -- giong breathing_worker.py"
    )
    return parser.parse_args()


args = parse_args()

# Hang doi tu ESP8266: (timestamp_pc, distance_cm)
# maxlen de tranh RAM tran khi worker nghi ma ESP8266 van gui
incoming = deque(maxlen=5000)

# ----------------------------------------------------------------
# Flask nho: chi nhan POST /distance tu ESP8266
# ----------------------------------------------------------------
receiver = Flask(__name__)

@receiver.route("/distance", methods=["POST"])
def receive_distance():
    data = request.get_json(silent=True)
    if not data or "distance_cm" not in data:
        return jsonify({"error": "Thieu distance_cm"}), 400

    dist = float(data["distance_cm"])
    # Dung timestamp may tinh (chinh xac hon millis() ESP8266 khi co network jitter)
    incoming.append((time.time(), dist))
    return jsonify({"ok": True}), 200

@receiver.route("/status", methods=["GET"])
def status():
    return jsonify({
        "buffer_size": len(incoming),
        "message": f"Dang thu thap. Can {args.interval:.0f}s du lieu de tinh BPM."
    })


# ----------------------------------------------------------------
def push_bpm(bpm_value):
    url = f"{args.api}/api/breathing"
    try:
        resp = requests.post(
            url,
            json={"bpm": round(bpm_value, 2), "source": "ultrasonic"},
            timeout=5,
        )
        if resp.status_code == 201:
            print(f"[ultrasonic] Da gui BPM={bpm_value:.2f} len API")
        else:
            print(f"[ultrasonic] API tra loi {resp.status_code}: {resp.text}")
    except requests.exceptions.RequestException as e:
        print(f"[ultrasonic] Khong gui duoc len API: {e}")


def process_block(block):
    """
    Xu ly 1 khoi 60 giay:
    1. Dao nguoc tin hieu: HC-SR04 do GIAM khi hit vao (long nguc phong)
       nhung ta can TANG de peak tuong ung voi 1 nhip tho day du.
       -> nhan -1 de dao nguoc.
    2. Chuan hoa ve trung binh 0 (bo troi DC).
    3. Ap dung CUNG pipeline voi ESP32-CAM: bandpass + find_peaks.
    """
    timestamps = [t for t, _ in block]
    distances  = [d for _, d in block]
    duration   = timestamps[-1] - timestamps[0]



    if duration <= 0:
        return None, None, None

    # Buoc 1: dao nguoc + chuan hoa
    mean_dist = sum(distances) / len(distances)
    signal = [-(d - mean_dist) for d in distances]
    # Ket qua: khi long nguc phong (khoang cach giam) -> signal tang -> peak

    # Buoc 2: bandpass 0.1-0.5 Hz (giong het signal_filter.py cho camera)
    # Truyen them timestamps de resample ve luoi thoi gian deu truoc khi
    # loc -- ESP8266 gui qua WiFi cung co the bi jitter giong ESP32-CAM.
    try:
        filtered = SignalFilter.smooth(
            signal, timestamps=timestamps, duration_seconds=duration
        )
        # Buoc 3: dem nhip (giong het breathing_rate.py cho camera)
        bpm, peaks = BreathingRateEstimator.estimate(filtered, duration)
        if len(peaks) >= 3:
            intervals = [peaks[i + 1] - peaks[i] for i in range(len(peaks) - 1)]
            mean_interval = sum(intervals) / len(intervals)
            std_interval = (sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)) ** 0.5
            regularity = std_interval / mean_interval
            if regularity > 0.5:
                print("[ultrasonic] Tin hieu khong deu (co the nin tho hoac nhieu), bo qua")
                return None, None, None
    except Exception as e:
        # FIX: khong de 1 khoi loi lam crash toan bo worker, giong
        # cach da sua trong breathing_worker.py.
        print(f"[ultrasonic] LOI khi tinh BPM cho khoi nay, bo qua: {type(e).__name__}: {e}")
        return None, None, None

    fps = len(signal) / duration
    print(
        f"[ultrasonic] Respiration Rate: {bpm:.2f} BPM "
        f"(fps={fps:.1f}, samples={len(signal)}, duration={duration:.1f}s, peaks={len(peaks)})"
    )

    return bpm, signal, list(filtered)


# ----------------------------------------------------------------
# Matplotlib: ve lai sau moi khoi (giong breathing_worker.py)
# ----------------------------------------------------------------
def setup_plot():
    plt.ion()
    fig, ax = plt.subplots(figsize=(10, 5))
    raw_line,      = ax.plot([], [], alpha=0.5, label="Raw Signal (dao nguoc + chuan hoa)")
    filtered_line, = ax.plot([], [], linewidth=2, label="Filtered Signal (bandpass)")
    ax.set_title("Ultrasonic Respiration Signal Analysis")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Chest motion (a.u.)")
    ax.legend()
    ax.grid(True)
    try:
        fig.canvas.manager.set_window_title("Ultrasonic Signal Analysis")
    except Exception:
        pass
    fig.show()
    return fig, ax, raw_line, filtered_line


def update_plot(fig, ax, raw_line, filtered_line, timestamps, raw_signal, filtered_signal):
    if not plt.fignum_exists(fig.number):
        return
    x = [t - timestamps[0] for t in timestamps]
    # filtered_signal co the da bi resample (do dai khac raw_signal) do
    # SignalFilter.smooth resample theo timestamps -- ve truc x rieng
    # cho duong filtered neu do dai khac voi x cua raw.
    if len(filtered_signal) == len(x):
        x_filtered = x
    else:
        import numpy as np
        x_filtered = np.linspace(0, x[-1] if x else 0, len(filtered_signal))
    raw_line.set_data(x, raw_signal)
    filtered_line.set_data(x_filtered, filtered_signal)
    ax.relim()
    ax.autoscale_view()
    fig.canvas.draw()
    fig.canvas.flush_events()


# ----------------------------------------------------------------
def processing_loop(fig, ax, raw_line, filtered_line):
    """Vong lap chinh: moi --interval giay lay khoi, xu ly, gui BPM."""
    print(f"[ultrasonic] Bat dau thu thap du lieu, tinh BPM moi {args.interval:.0f} giay...")
    print(f"[ultrasonic] Dang lang nghe tai port {args.port}. ESP8266 can POST toi:")
    print(f"             http://<IP_MAY_TINH>:{args.port}/distance")

    block_start = time.time()

    while True:
        # Giu matplotlib phan hoi
        if plt.fignum_exists(fig.number):
            fig.canvas.flush_events()

        time.sleep(0.1)

        now = time.time()
        if now - block_start < args.interval:
            continue

        # Lay tat ca sample trong khoi vua xong
        block = [(t, d) for t, d in incoming if block_start <= t < now]

        if len(block) < 10:
            print(f"[ultrasonic] Chi co {len(block)} sample trong khoi, bo qua. "
                  "Kiem tra ESP8266 co gui du lieu khong (GET /status de xem buffer).")
            block_start = now
            continue

        bpm, raw_signal, filtered_signal = process_block(block)

        if bpm is not None and bpm > 0:
            push_bpm(bpm)
            timestamps = [t for t, _ in block]
            update_plot(fig, ax, raw_line, filtered_line, timestamps, raw_signal, filtered_signal)

        block_start = now


# ----------------------------------------------------------------
if __name__ == "__main__":
    import threading

    fig, ax, raw_line, filtered_line = setup_plot()

    # Flask receiver chay o thread nen, khong block vong xu ly chinh
    flask_thread = threading.Thread(
        target=lambda: receiver.run(host="0.0.0.0", port=args.port, debug=False, use_reloader=False),
        daemon=True
    )
    flask_thread.start()
    print(f"[ultrasonic] Flask receiver da khoi dong tren port {args.port}")

    try:
        processing_loop(fig, ax, raw_line, filtered_line)
    except KeyboardInterrupt:
        print("[ultrasonic] Da dung theo yeu cau (Ctrl+C)")
    finally:
        plt.close(fig)