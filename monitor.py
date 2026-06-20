import time

from src.tools.alerts import check_alerts
from src.tools.telegram_sender import send_telegram_message

from src.tools.container_check import (
    check_vllm,
    check_litellm,
    check_qdrant,
    check_open_webui,
)

from src.tools.service_states import (
    load_states,
    save_states,
)


CHECK_INTERVAL = 30


def get_current_states():

    return {
        "vllm": check_vllm(),
        "litellm": check_litellm(),
        "qdrant": check_qdrant(),
        "open-webui": check_open_webui(),
    }


def monitor():

    print("InfraBot Monitor Started")

    previous = load_states()

    while True:

        try:

            current = get_current_states()

            #
            # Recovery / Failure Detection
            #

            for service, status in current.items():

                old_status = previous.get(service)

                if (
                    old_status
                    and old_status != status
                ):

                    if "healthy" in status:

                        send_telegram_message(
                            f"✅ InfraBot Recovery\n\n"
                            f"{service} healthy again"
                        )

                        print(
                            f"{service} recovered"
                        )

                    else:

                        send_telegram_message(
                            f"🚨 InfraBot Alert\n\n"
                            f"{service} unhealthy"
                        )

                        print(
                            f"{service} failed"
                        )

            #
            # General Alerts
            #

            alerts = check_alerts()

            if alerts != "No alerts":

                send_telegram_message(
                    f"🚨 InfraBot Alert\n\n"
                    f"{alerts}"
                )

            save_states(current)

            previous = current

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
