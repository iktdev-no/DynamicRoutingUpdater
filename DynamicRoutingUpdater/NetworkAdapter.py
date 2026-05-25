import logging
import re
import netifaces
from netaddr import IPAddress
from typing import List, Optional
from .objects import IpData, Netstated
import subprocess

logging.basicConfig(level=logging.INFO)

class NetworkAdapter:
    name: str = None # Network Adapter name

    def __init__(self, name) -> None:
        self.name = name
    
    def getIpData(self) -> IpData:
        gateway = self.getGateway()
        ipAddress = self.getIpAddress()
        subnet = self.getSubnet()
        cidr = self.getCidr(subnet)
        netmask = self.getNetmask()
        return IpData(
            name=self.name,
            gateway=gateway,
            ip=ipAddress,
            subnet=subnet,
            cidr=cidr,
            netmask=netmask
        )
        

    def getGateway(self) -> Optional[str]:
        gws = netifaces.gateways()
        for gw in gws:
            try:
                gwstr: str = str(gw)
                if 'default' not in gwstr:
                    entries = gws[gw]
                    for entry in entries:
                        if self.name in entry[1]:
                            return entry[0]
            except:
                logging.error(f"getGateway => {gw}")
        # If this is hit, then it could not find the gateway using traditional means
        logging.info("Using fallback to get gateway")
        netst = self.parseNetstat(nic_name=self.name)
        routable = [line for line in netst if "G".lower() in line.flags.lower()]
        use_route: Netstated = next(iter(routable), None)
        if (use_route is not None):
            return use_route.gateway
        return None
    
    def getNetmask(self) -> Optional[str]:
        gw = self.getGateway()
        try:
            netmask = gw[:gw.rfind(".")+1]+"0"
            return netmask
        except:
            logging.error(f"getNetmask => {gw}")
            pass
        return None

    def getIpAddress(self) -> Optional[str]:
        try:
            iface = netifaces.ifaddresses(self.name)
            entry = iface[netifaces.AF_INET][0]
            return entry["addr"]
        except:
            pass
        return None

    def getSubnet(self) -> Optional[str]:
        try:
            iface = netifaces.ifaddresses(self.name)
            entry = iface[netifaces.AF_INET][0]
            return entry["netmask"]
        except:
            pass
        return None

    def getCidr(self, subnet: str) -> Optional[str]:
        try:
            return IPAddress(subnet).netmask_bits()
        except:
            pass
        return None



    def parseNetstat(self, nic_name: str) -> List[Netstated]:
            """
            Moderne erstatning for netstat ved bruk av 'ip route'.
            Returnerer samme datastruktur som tidligere.
            """
            try:
                # Henter ruter for spesifikt interface i JSON-format
                cmd = ["ip", "-4", "-j", "route", "show", "dev", nic_name]
                output = subprocess.check_output(cmd).decode('utf-8')
                data = json.loads(output)
                
                entries: List[Netstated] = []
                for item in data:
                    # Mapper JSON-verdier til streng-formatet Netstated forventer
                    entries.append(
                        Netstated(
                            destination=item.get("dst", "default"),
                            gateway=item.get("gateway", "0.0.0.0"),
                            genmask=str(item.get("prefixlen", "0")), 
                            flags="UG" if item.get("gateway") else "U",
                            metric=str(item.get("metric", "0")),
                            ref="0",
                            use="0",
                            iface=nic_name
                        )
                    )
                return entries
            except Exception:
                # Logg feil hvis kommandoen feiler, returner tom liste som før
                logging.error(f"Failed to parse routes for {nic_name} via 'ip route'")
                return []
        
