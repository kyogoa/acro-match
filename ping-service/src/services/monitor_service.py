import schedule
import time
from services.alert_service import AlertService
from services.ping_service import PingService
import os
from dotenv import load_dotenv
load_dotenv()

class MonitorService:
    def __init__(self):
        # 遅延インポートで循環インポートを回避
        self.ping_service = PingService()
        self.alert_service = AlertService(
            sender_email=os.environ.get("SMTP_USER"),
            sender_password=os.environ.get("SMTP_PASSWORD"),
            smtp_server=os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
            smtp_port=int(os.environ.get("SMTP_PORT", 587))
        )

    def monitor_http(self, url):
        """
        HTTP監視を実行し、結果を出力する。
        """
        print(f"Debug: Starting HTTP monitoring for {url}")
        result = self.ping_service.check_http(url)
        print(f"Debug: Monitoring result -> {result}")

        if "reachable" not in result:
            self.alert_service.send_email(
                recipient_email="recipient_email@example.com",
                subject="Server Down Alert",
                message=f"Alert: The server at {url} is not reachable.\n\nDetails:\n{result}"
            )

    def start_monitoring(self, url, interval=5):
        """
        定期的にHTTP監視を実行する。
        """
        schedule.every(interval).minutes.do(self.monitor_http, url=url)
        print(f"Debug: Scheduled HTTP monitoring every {interval} minutes for {url}")

        while True:
            schedule.run_pending()
            time.sleep(1)

def monitor_server(url, interval=300):
    ping_service = PingService()
    while True:
        result = ping_service.check_http(url)
        print(result)  # ログはすでに ping_service 内で記録される
        time.sleep(interval)

if __name__ == "__main__":
    monitor_server("https://acro-match-w8t0.onrender.com", interval=300)  # 5分ごとに監視