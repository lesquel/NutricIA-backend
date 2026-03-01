"""Seed script entrypoint — allows `python -m scripts.seed`."""

from scripts import main

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
