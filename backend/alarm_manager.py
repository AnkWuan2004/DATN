from datetime import datetime

from email_sender import send_breathing_alert

LOW_THRESHOLD = 5
HIGH_THRESHOLD = 25

mail_sent = False


def process(bpm, image_path):

    global mail_sent

    print("=" * 60)
    print(f"[Alarm] BPM nhận được : {bpm:.2f}")
    print(f"[Alarm] Thời gian     : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"[Alarm] Image        : {image_path}")
    print("=" * 60)

    # Có cảnh báo
    if bpm < LOW_THRESHOLD or bpm > HIGH_THRESHOLD:

        if not mail_sent:

            print("[Alarm] Phát hiện bất thường -> Chuẩn bị gửi email")

            try:
                send_breathing_alert(
                    bpm=bpm,
                    image_path=image_path
                )

                mail_sent = True

                print("[Alarm] Đã gửi email thành công")

            except Exception as e:

                print("[Alarm] Gửi email thất bại")
                print(e)

        else:

            print("[Alarm] Đã gửi email trước đó, bỏ qua.")

    # Bình thường
    else:

        if mail_sent:
            print("[Alarm] Nhịp thở đã trở về bình thường -> Reset trạng thái")

        mail_sent = False