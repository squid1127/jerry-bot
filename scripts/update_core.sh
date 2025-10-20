#!/usr/bin/env bash
# Using poetry, forcefully redownload squid-core
poetry remove squid-core
poetry add "squid-core @ git+https://github.com/squid1127/squid-core.git@main"