import logging


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # google-genai / httpx are chatty at INFO.
    for noisy in ("httpx", "google_genai", "websockets"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
