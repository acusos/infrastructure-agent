import time

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

from src.tools.auto_recovery import (
    recover_service,
)


CHECK_INTERVAL = 30


def get_current_states():

    return {
        "vllm": check_vllm(),
        "litellm": check_litellm(),
        "qdrant": check_qdrant(),
        "open-webui": check_open_webui(),
    }


def is_healthy(status):

    return (
        status.endswith(" healthy")
    )


def monitor():

    print("InfraBot Monitor Started")

    previous = load_states()

    while True:

        try:

            current = get_current_states()

            for service, status in current.items():

                old_status = previous.get(service)

                if (
                    old_status
                    and old_status != status
                ):

                    old_healthy = is_healthy(
                        old_status
                    )

                    new_healthy = is_healthy(
                        status
                    )

                    #
                    # Recovery
                    #

                    if (
                        not old_healthy
                        and new_healthy
                    ):

                        send_telegram_message(
                            f"✅ InfraBot Recovery\n\n"
                            f"{service} healthy again"
                        )

                        print(
                            f"{service} recovered"
                        )

                    #
                    # Failure
                    #

                    elif (
                        old_healthy
                        and not new_healthy
                    ):

                        send_telegram_message(
                            f"🚨 InfraBot Alert\n\n"
                            f"{service} unhealthy\n\n"
                            f"Attempting recovery..."
                        )

                        success, message = (
                            recover_service(service)
                        )

                        if success:

                            send_telegram_message(
                                f"⚠️ InfraBot Auto Recovery\n\n"
                                f"{message}"
                            )

                        else:

                            send_telegram_message(
                                f"🚨 InfraBot Critical\n\n"
                                f"{message}"
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
