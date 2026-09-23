"""Seed the stand's panel: one AmneziaWG profile, one Xray, one with both.

kickstart.sh pipes this into python inside the panel container, where it runs
through the panel's own service layer, so the peers and the client reach the
fake host exactly as a profile issued from the browser would. awg0 and
reality-443 are configured and enabled for it; awg1 and reality-8443 stay as
discovered, so the configure screens still have something to do.
"""

from __future__ import annotations

from sqlmodel import Session, select

from awg_panel import db, service
from awg_panel.config import Settings
from awg_panel.models import Inbound, Interface, Profile
from awg_panel.schemas import (
    AwgRequest,
    InboundUpdate,
    InterfaceUpdate,
    ProfileCreate,
    XrayRequest,
)

# Not the keys fakehost.py puts on awg0: the agent refuses a peer it already has.
PEER_A = "OPzhTI0i6NqQJZ52+wAmTQemP7gJm3yRNKWaZYKFy4o="
PEER_B = "agqavF5oO8KIY13jpwOWWxI+HQ3uwmDQ9+5m0JR4ISw="
UUID_CAROL = "3c1d9e2f-6a4b-4c8d-9e7f-1a2b3c4d5e6f"
UUID_BOB = "8e7f6a5b-4c3d-4e2f-8a1b-9c0d1e2f3a4b"
ENDPOINT = "ams-1.example.net"


def main() -> None:
    """Enable what the profiles need and issue them, once per stand."""
    settings = Settings()
    with Session(db.build_engine(settings)) as session:
        if session.exec(select(Profile)).first() is not None:
            print("seed: the panel already has profiles, left alone")
            return

        service.probe_agents(session, settings)
        awg0 = session.exec(select(Interface).where(Interface.name == "awg0")).one()
        service.update_interface(
            session,
            settings,
            int(awg0.id or 0),
            InterfaceUpdate(enabled=True, endpoint_host=ENDPOINT),
        )
        inbound = session.exec(
            select(Inbound).where(Inbound.tag == "reality-443")
        ).one()
        service.update_inbound(
            session,
            settings,
            int(inbound.id or 0),
            InboundUpdate(enabled=True, endpoint_host=ENDPOINT, label="ams-1 reality"),
        )

        awg = int(awg0.id or 0)
        xray = int(inbound.id or 0)
        for body in (
            ProfileCreate(
                name="alice-laptop",
                note="MacBook",
                awg=AwgRequest(interface_id=awg, public_key=PEER_A),
            ),
            ProfileCreate(
                name="carol",
                note="Xray only",
                xray=XrayRequest(inbound_id=xray, id=UUID_CAROL),
            ),
            ProfileCreate(
                name="bob-phone",
                note="Pixel 8",
                awg=AwgRequest(interface_id=awg, public_key=PEER_B),
                xray=XrayRequest(inbound_id=xray, id=UUID_BOB),
            ),
        ):
            issued = service.create_profile(session, settings, body)
            print(f"seed: profile {issued.profile.name} issued")


main()
