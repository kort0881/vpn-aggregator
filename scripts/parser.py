"""
VPN Config Parser for VLESS, VMess, Shadowsocks
"""
import re
import json
import base64
from urllib.parse import parse_qs, unquote
from typing import Optional, Dict, List
from dataclasses import dataclass, field


@dataclass
class VPNNode:
    """Parsed VPN node"""
    protocol: str  # vless, vmess, ss
    host: str
    port: int
    uuid: Optional[str] = None
    password: Optional[str] = None
    remark: str = ""
    tls: bool = False
    sni: Optional[str] = None
    extra: Dict = field(default_factory=dict)


class ConfigParser:
    """Parser for VPN configs"""

    @staticmethod
    def parse_vless(uri: str) -> Optional[VPNNode]:
        """
        Parse VLESS URI
        Format: vless://uuid@host:port?params#remark
        """
        try:
            if "#" in uri:
                uri_part, remark = uri.rsplit("#", 1)
                remark = unquote(remark.strip())
            else:
                uri_part, remark = uri, ""

            match = re.match(r"vless://([^@]+)@([^:]+):(\d+)(.*)", uri_part)
            if not match:
                return None

            uuid, host, port, query_part = match.groups()
            port = int(port)

            params: Dict[str, str] = {}
            if query_part.startswith("?"):
                raw = parse_qs(query_part[1:])
                params = {k: v[0] if isinstance(v, list) else v for k, v in raw.items()}

            return VPNNode(
                protocol="vless",
                host=host,
                port=port,
                uuid=uuid,
                remark=remark,
                tls=params.get("security") == "tls",
                sni=params.get("sni"),
                extra=params,
            )
        except Exception:
            return None

    @staticmethod
    def parse_vmess(uri: str) -> Optional[VPNNode]:
        """
        Parse VMess URI
        Format: vmess://base64(json_config)
        """
        try:
            if not uri.startswith("vmess://"):
                return None

            b64_part = uri[8:]
            json_str = base64.b64decode(b64_part).decode("utf-8")
            config = json.loads(json_str)

            return VPNNode(
                protocol="vmess",
                host=config.get("add", ""),
                port=int(config.get("port", 0)),
                uuid=config.get("id", ""),
                remark=config.get("ps", ""),
                tls=config.get("tls") == "tls",
                sni=config.get("sni"),
                extra=config,
            )
        except Exception:
            return None

    @staticmethod
    def parse_ss(uri: str) -> Optional[VPNNode]:
        """
        Parse Shadowsocks URI
        Format: ss://base64(method:password)@host:port#remark
        """
        try:
            if not uri.startswith("ss://"):
                return None

            if "#" in uri:
                uri_part, remark = uri.rsplit("#", 1)
                remark = unquote(remark.strip())
            else:
                uri_part, remark = uri, ""

            uri_part = uri_part[5:]  # remove 'ss://'

            if "@" not in uri_part:
                return None

            cred_part, addr_part = uri_part.split("@", 1)
            try:
                decoded = base64.b64decode(cred_part).decode("utf-8")
                method, password = decoded.split(":", 1)
            except Exception:
                if ":" in cred_part:
                    method, password = cred_part.split(":", 1)
                else:
                    method, password = cred_part, ""

            host, port = addr_part.split(":", 1)
            port = int(port)

            return VPNNode(
                protocol="ss",
                host=host,
                port=port,
                password=password,
                remark=remark,
                extra={"method": method},
            )
        except Exception:
            return None

    @staticmethod
    def parse(uri: str) -> Optional[VPNNode]:
        """Auto-detect and parse any supported protocol"""
        uri = uri.strip()
        if uri.startswith("vless://"):
            return ConfigParser.parse_vless(uri)
        if uri.startswith("vmess://"):
            return ConfigParser.parse_vmess(uri)
        if uri.startswith("ss://"):
            return ConfigParser.parse_ss(uri)
        return None

    def parse_text(self, text: str, source: str = "unknown") -> List[VPNNode]:
        """
        Parse whole text block into list of VPNNode.
        Каждой ноде проставляем extra['source_name'] и базовый extra['provider_id'].
        """
        nodes: List[VPNNode] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            node = self.parse(line)
            if not node:
                continue

            # базовый источник = имя файла/агрегатора
            node.extra.setdefault("source_name", source)
            # базовый провайдер = тот же, пока нет hunter'а
            node.extra.setdefault("provider_id", source)

            nodes.append(node)
        return nodes

    @staticmethod
    def rebuild_uri(node: VPNNode, new_remark: Optional[str] = None) -> str:
        """Rebuild URI from VPNNode with optionally new remark"""
        remark = new_remark if new_remark is not None else node.remark

        if node.protocol == "vless":
            params = "&".join(
                f"{k}={v}" for k, v in node.extra.items() if k not in ["uuid"]
            )
            uri = f"vless://{node.uuid}@{node.host}:{node.port}"
            if params:
                uri += f"?{params}"
            if remark:
                uri += f"#{remark}"
            return uri

        if node.protocol == "vmess":
            config = node.extra.copy()
            config.update(
                {
                    "add": node.host,
                    "port": str(node.port),
                    "id": node.uuid,
                    "ps": remark,
                }
            )
            json_str = json.dumps(config, ensure_ascii=False)
            b64 = base64.b64encode(json_str.encode()).decode()
            return f"vmess://{b64}"

        if node.protocol == "ss":
            method = node.extra.get("method", "aes-256-gcm")
            cred = f"{method}:{node.password}"
            cred_b64 = base64.b64encode(cred.encode()).decode()
            uri = f"ss://{cred_b64}@{node.host}:{node.port}"
            if remark:
                uri += f"#{remark}"
            return uri

        return ""

