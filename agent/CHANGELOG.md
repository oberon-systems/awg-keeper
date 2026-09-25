## awg-keeper-agent-v0.5.0 (2026-09-25)

### Features

- **agent**: set amneziawg 3.1 obfuscation, rename xray clients

### Build

- **deps**: fit eslint 10 and python 3.14
- **deps**: Update uv-build requirement in /agent (#13)
- **deps**: Bump the pip group across 3 directories with 4 updates (#12)

## awg-keeper-agent-v0.4.0 (2026-09-23)

### Features

- **agent**: report inbounds and xray stats

## awg-keeper-agent-v0.3.4 (2026-09-18)

### Bug Fixes

- **agent**: stop awg segfaults, survive a denied conf dir

## awg-keeper-agent-v0.3.3 (2026-09-18)

### Bug Fixes

- **agent**: report addresses, keep awg-quick settings on persist

## awg-keeper-agent-v0.3.2 (2026-09-18)

### Bug Fixes

- **agent**: reach the UAPI socket through a root proxy

## awg-keeper-agent-v0.3.1 (2026-09-17)

### Bug Fixes

- **agent**: drop CAP_NET_ADMIN from the unit

## awg-keeper-agent-v0.3.0 (2026-09-17)

### Features

- **agent**: check interfaces on start, report key, port and obfuscation

## awg-keeper-agent-v0.2.0 (2026-09-16)

### Features

- **agent**: log every request, report interfaces in /v1/status

### Build

- **web**: bump version 0.1.0 -> 0.2.0
- **agent, web**: update cz configs
- **bumo**: remove useless hooks

## awg-keeper-agent-v0.1.1 (2026-09-02)

### Bug Fixes

- **agent**: rpm/deb packaging fixed

### Build

- **agent**: bump the agent to 0.1.1

## awg-keeper-agent-v0.1.0 (2026-09-02)

### Features

- **agent**: http agent for awg peers and xray users

### Bug Fixes

- **agent**: refuse a misspelled AWG_KEEPER_ variable

### Build

- **agent**: bump the agent to 0.1.0
- **agent**: bump the agent version with cz
- **agent**: rpm and deb from one nfpm description
