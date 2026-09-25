# Project Roadmap

## Agent

sub-project tag: awg-keeper-agent-v0.5.0

- [x] code basics
  - FastAPI (HTTP)
  - configs via Pydantic2
  - Auth by pre-set token (PSK)
  - Auth by pre-set SRC IPs (subnets)
  - awg
    - add profile
    - delete profile
    - show profile
    - list profiles
  - xray/reality users (add, delete, show, list)
  - health, state, structured JSON logs with a request id

- [x] build
  - build in docker
  - one binary for agent (shiv zipapp on the distro python)
  - pack as rpm
  - pack as deb
  - deb/rpm create directories, configs, users and systemd unit

- [x] ci/cd
  - github action for build both rpm and deb by changing sub-project tag (uwe cache)
  - packages attached to a github release named after the tag

## web / panel

sub-project tag: awg-keeper-web-v0.7.0

- [x] code basics
  - FastAPI (HTTP)
  - configs via Pydantic2
  - SPA for web ui
  - base auth with pre-set creds
  - base auth with src ips (subnets)
  - store state in sqlite (SQLModel)
  - docker/docker-compose ready
  - alembic migrations from the first commit
  - client to the agent: a profile pushes its peer to the node
  - keys generated in the browser, config and QR rendered there

- [x] build
  - docker image

- [x] ci/cd
  - github action for build and push the image by changing sub-project tag (uwe cache)

## Pre-production features

- [ ] **agent**: added multi-agent support: registration, lease etc

- [ ] **web**: at first run use admin/admin and require password change, store encrypted passwords in db

- [ ] **web**: auth: added RBAC with admin, manager, reader and users groups

- [ ] **base**: on stats page able to user to sign-in with email at first, then should be able to reroll profiles

## Production Hardening

- [ ] resource quotas

- [ ] users connections security audit

- [ ] alerting

- [ ] monitoring
