import time

from src.tools.alerts import check_alerts
from src.tools.telegram_sender import send_telegram_message


CHECK_INTERVAL = 300


def monitor():

    print("InfraBot Monitor Started")

    last_alert = None

    while True:

        try:

            result = check_alerts()

            if result != "No alerts":

                if result != last_alert:

                    message = (
                        "🚨 InfraBot Alert\n\n"
                        f"{result}"
                    )

                    send_telegram_message(
                        message
                    )

                    print(
                        f"Alert sent: {result}"
                    )

                    last_alert = result

            else:

                last_alert = None

            time.sleep(
                CHECK_INTERVAL
            )

        except Exception as e:

            print(
                f"Monitor error: {e}"
            )

            time.sleep(
                CHECK_INTERVAL
            )


if __name__ == "__main__":

    monitor()
