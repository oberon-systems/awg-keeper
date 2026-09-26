## awg-keeper-web-v0.7.2 (2026-09-26)

### Bug Fixes

- **web**: generate xray ids over plain http, reroll halves apart

## awg-keeper-web-v0.7.1 (2026-09-25)

### Bug Fixes

- **web**: size the profile status and actions by content

## awg-keeper-web-v0.7.0 (2026-09-25)

### Features

- **web**: edit profiles and obfuscation, mark rerolls

### Build

- **deps**: fit eslint 10 and python 3.14
- **web**: bump version 0.5.0 -> 0.6.0
- **deps**: Update uv-build requirement in /web
- **deps**: Bump the pip group across 3 directories with 4 updates (#12)
- **deps**: Bump vite from 6.4.3 to 8.3.0 in /web/ui (#11)
- **deps**: Bump eslint from 9.39.5 to 10.11.0 in /web/ui
- **deps**: Bump @vitejs/plugin-react from 4.7.0 to 6.1.1 in /web/ui
- **deps**: Bump the npm group in /web/ui with 6 updates
- **deps**: Bump node from 22-alpine to 25-alpine in /web
- **deps**: Bump the docker group across 2 directories with 1 update

## awg-keeper-web-v0.6.0 (2026-09-25)

### Features

- **web**: issue amnezia keys, toggle and reroll profiles

## awg-keeper-web-v0.5.0 (2026-09-23)

### Features

- **web**: serve the own stats page on /stats
- **web**: build the profiles page on the mockup
- **web**: issue xray clients and sample profile stats
- **web**: build the interface modal on the mockup
- **web**: build the dashboard on the mockup
- **web**: rebuild the sign in page on the mockup

## awg-keeper-web-v0.4.0 (2026-09-18)

### Features

- **web**: take the interface address from the agent

## awg-keeper-web-v0.3.0 (2026-09-17)

### Features

- **web**: status page, background healthchecks, agents from env

## awg-keeper-web-v0.2.0 (2026-09-16)

### Features

- **web**: agents tab, calls by node endpoint, agent then interface
- **provisioning**: secrets generator added

### Build

- **agent, web**: update cz configs
- **bumo**: remove useless hooks

## awg-keeper-web-v0.1.0 (2026-09-02)

### Features

- **ui**: sign in, profiles, and a config the web never sees
- **web**: profiles, peers and the client to the agent

### Bug Fixes

- **web**: give the pool tests the profile a peer needs
- **web**: refuse a misspelled AWG_PANEL_ variable

### Build

- **web**: bump the web to 0.1.0
- **web**: name the scope after the directory
- **web**: build the interface from a lockfile
- **web**: one image, compose, and a version of its own
