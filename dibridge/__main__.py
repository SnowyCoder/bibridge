import click
import ipaddress
import logging
import threading

from openttd_helpers import click_helper
from openttd_helpers.logging_helper import click_logging
from openttd_helpers.sentry_helper import click_sentry

from . import discord
from . import irc

log = logging.getLogger(__name__)


@click_helper.command()
@click_logging  # Should always be on top, as it initializes the logging
@click_sentry
@click.option("--discord-token", help="Discord bot token to authenticate.", required=True)
@click.option("--discord-channel-id", help="Discord channel ID to relay to.", type=int)
@click.option("--irc-host", help="IRC host to connect to.", required=True)
@click.option("--irc-port", help="IRC SSL port to connect to.", default=6697, type=int)
@click.option("--irc-nick", help="IRC nick to use.", required=True)
@click.option("--irc-channel", help="IRC channel to relay to, as 'discord_id=irc_channel,...', without the first '#' on IRC.")
@click.option("--channel-map", help="Discord->IRC channel lists to relay, without the first '#'.")
@click.option("--irc-puppet-ip-range", help="An IPv6 CIDR range to use for IRC puppets. (2001:A:B:C:D::/80)")
@click.option("--irc-puppet-postfix", help="Postfix to add to IRC puppet nicknames (default: none).", default="")
@click.option("--irc-ignore-list", help="IRC nicknames to not relay messages for (comma separated, case-insensitive).")
@click.option(
    "--irc-idle-timeout",
    help="IRC puppet idle timeout, in seconds (default: 2 days).",
    default=60 * 60 * 24 * 2,
    type=int,
)
def main(
    discord_token,
    discord_channel_id,
    irc_host,
    irc_port,
    irc_nick,
    irc_channel,
    channel_map,
    irc_puppet_ip_range,
    irc_puppet_postfix,
    irc_ignore_list,
    irc_idle_timeout,
):
    if irc_puppet_ip_range:
        irc_puppet_ip_range = ipaddress.ip_network(irc_puppet_ip_range)
        if irc_puppet_ip_range.num_addresses < 2**32:
            raise Exception("--irc-puppet-ip-range needs to be an IPv6 CIDR range of at least /96 or more.")

    if irc_ignore_list:
        irc_ignore_list = [nickname.strip().lower() for nickname in irc_ignore_list.split(",") if nickname.strip()]
    if not irc_ignore_list:
        irc_ignore_list = []

    if channel_map:
        if discord_channel_id or irc_channel:
            raise Exception("If you're using channel_map, please don't use the older options")

        disc_to_irc = dict()
        irc_to_disc = dict()
        for c in channel_map.split(','):
            disc_chan, irc_chan = c.strip().split('=')
            disc_chan = int(disc_chan)
            irc_chan = f'#{irc_chan}'
            disc_to_irc[disc_chan] = irc_chan
            irc_to_disc[irc_chan] = disc_chan
    elif discord_channel and irc_channel:
        irc_channel = f'#{irc_channel}'
        disc_to_irc = {discord_channel_id: irc_channel}
        irc_to_disc = {irc_channel: discord_channel_id}
    else:
        raise Exception("Please either use --channel-map or --irc-channel and --discord-channel-id")

    thread_d = threading.Thread(target=discord.start, args=[discord_token, disc_to_irc])
    thread_i = threading.Thread(
        target=irc.start,
        args=[
            irc_host,
            irc_port,
            irc_nick,
            irc_to_disc,
            irc_puppet_ip_range,
            irc_puppet_postfix,
            irc_ignore_list,
            irc_idle_timeout,
        ],
    )

    thread_d.start()
    thread_i.start()

    thread_d.join()
    thread_i.join()


if __name__ == "__main__":
    main(auto_envvar_prefix="DIBRIDGE")
