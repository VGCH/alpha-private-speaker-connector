"""Сетевые утилиты Alpha Speaker."""
from __future__ import annotations

import ipaddress


def speaker_configuration_url(address: str | None) -> str | None:
    """Вернуть URL веб-панели колонки на TCP-порту 8000.

    gRPC context.peer() обычно возвращает:
      - ipv4:192.168.1.20:54321
      - ipv6:[2001:db8::20]:54321

    Также поддерживаются сохранённые значения в виде чистого IP-адреса.
    Для неизвестного или непарсящегося адреса возвращается None.
    """
    if not address or not isinstance(address, str):
        return None

    value = address.strip()
    if not value or value.lower() in {"unknown", "none", "n/a"}:
        return None

    host: str | None = None

    if value.startswith("ipv4:"):
        # Формат gRPC: ipv4:<IPv4>:<client-port>
        peer = value[len("ipv4:"):]
        host, separator, _port = peer.rpartition(":")
        if not separator:
            host = peer

    elif value.startswith("ipv6:"):
        # Формат gRPC: ipv6:[<IPv6>]:<client-port>
        peer = value[len("ipv6:"):]
        if peer.startswith("[") and "]" in peer:
            host = peer[1:peer.index("]")]
        else:
            # На случай старых сохранённых адресов без квадратных скобок.
            try:
                ipaddress.ip_address(peer)
                host = peer
            except ValueError:
                candidate, separator, port = peer.rpartition(":")
                if separator and port.isdigit():
                    host = candidate

    elif value.startswith("[") and "]" in value:
        # Стандартная запись IPv6 [address]:port.
        host = value[1:value.index("]")]

    else:
        # Чистый IP; если передан IPv4 с портом — отделяем порт.
        try:
            ipaddress.ip_address(value)
            host = value
        except ValueError:
            if value.count(":") == 1:
                candidate, _port = value.rsplit(":", 1)
                host = candidate

    if not host:
        return None

    try:
        parsed_ip = ipaddress.ip_address(host)
    except ValueError:
        return None

    if parsed_ip.version == 6:
        return f"http://[{parsed_ip.compressed}]:8000"
    return f"http://{parsed_ip.compressed}:8000"
