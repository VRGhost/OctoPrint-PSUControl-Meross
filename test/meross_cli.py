"""This is an interactive test script to try `meross_client.py` without doing a complete Octoprint deployment."""

import argparse
import logging

from pathlib import Path

from octoprint_psucontrol_meross import meross_client


def main(args):
    cache_fname = Path(args["cache_fname"])
    client = meross_client.OctoprintPsuMerossClient(
        cache_file=cache_fname,
        logger=logging.getLogger("OctoprintPsuMerossClient"),
    )
    login_rv = client.login(args["username"], args["password"], sync=True)
    print(f"Login result: {login_rv!r}")
    mode = args["mode"]
    if mode == "list":
        print("Listing all devices...")
        for el in client.list_devices():
            print(el)
    elif mode == "control":
        client.set_device_state(
            uuid=args["uuid"],
            state=bool(args["state"]),
        )
    else:
        raise NotImplementedError(mode)


def get_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True, help="Meross cloud username")
    parser.add_argument("--password", required=True, help="Meross cloud password")
    parser.add_argument(
        "--cache-fname",
        default="./meross_cloud_cache.tmp",
        help="Cache file for meross cloud auth",
    )
    subp = parser.add_subparsers(title="mode")

    list_p = subp.add_parser("list")
    list_p.set_defaults(mode="list")

    control_p = subp.add_parser("control")
    control_p.set_defaults(mode="control")
    control_p.add_argument("--uuid", required=True, help="Device UUID")
    control_p.add_argument("--state", type=int, help="On (1) or Off (0)")
    return parser


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    args = get_argument_parser().parse_args()
    main(args.__dict__)
