"""This is an interactive test script to try `meross_client.py` without doing a complete Octoprint deployment."""

import argparse
import logging
import time

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
            args["uuid"],
            state=bool(args["state"]),
        )
    elif mode == "is_on":
        for _ in range(100):
            print(client.is_on(args["uuid"]))
            time.sleep(10)
    elif mode == "test0":
        # I have one device downstream from another.
        upstream_dev = "1812079276197125182534298f18d174::0"
        downstream_dev = "21033062638419258h1848e1e9685d07::0"
        # turn off upstream
        client.set_device_state(upstream_dev, 0)
        print("Upstream OFF")
        time.sleep(20)
        # attempt to turn the downstream dev on
        # (should fail as the dev isn't powered)
        print("Trying to turn downstream ON (should fail)")
        client.set_device_state(downstream_dev, 1)
        time.sleep(5)
        client.set_device_state(upstream_dev, 1)
        print("Upstream ON (downstream should come online)")
        time.sleep(50)
        # attempt to turn the downstream dev on
        # (should succeed as the upstream is now ON)
        print("Turning downstream ON")
        client.set_device_state(downstream_dev, 1)
    elif mode == "test1":
        client.set_device_state("1812079276197125182534298f18d174::0", 0)
        # just idle for a while
        time.sleep(240)
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

    is_on_p = subp.add_parser("is_on")
    is_on_p.set_defaults(mode="is_on")
    is_on_p.add_argument("--uuid", required=True, help="Device UUID")

    test_p = subp.add_parser("test0")
    test_p.set_defaults(mode="test0")

    test_p = subp.add_parser("test1")
    test_p.set_defaults(mode="test1")
    return parser


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    args = get_argument_parser().parse_args()
    main(args.__dict__)
