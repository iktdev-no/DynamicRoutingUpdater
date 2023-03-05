from io import TextIOWrapper
import json
import random
from threading import Thread
import threading
from typing import List

from ._DynamicIpWatcherAction import _DynamicIpWatcherAction
import os, sys, time, re, errno
import netifaces 
       

class DynamicRoutingUpdater:
    """DynamicRoutingUpdater, modify routing table
    """
    dipwa: _DynamicIpWatcherAction = None
    
    configuredTables = {}
    tableName = "direct"
    
    nics: List[str] = []
    
    threads: List[Thread] = []
    
    
    def flipper(self) -> str:
        faces: List[str] = [
            "(╯°□°）╯︵ ┻━┻",
            "(┛◉Д◉)┛彡┻━┻",
            "(ノಠ益ಠ)ノ彡┻━┻",
            
            "(ノ｀´)ノ ~┻━┻",
            "┻━┻ ︵ヽ(`Д´)ﾉ︵ ┻━┻"
        ]
        return random.choice(faces)
    
    def __init__(self) -> None:
        """
        """
        sys.stdout.write(f"{self.flipper()}\n")
        sys.stdout.write("Loading up Dynamic Routing Updater\n")
        sys.stdout.write("Reading configuration\n")
        reference = json.load(open("reference.json"))
        self.nics.extend(reference["adapter"])
        desiredTableName: str = reference["tableName"]
        if desiredTableName != "":
            sys.stdout.write(f"Using desired table name {desiredTableName}\n")
            self.tableName = desiredTableName
        else:
            sys.stdout.write(f"Using DEFAULT table name {self.tableName}\n")
            
        sys.stdout.write("Dynamic Routing Updater will watch the following:\n")
        for toWatch in self.nics:
            sys.stdout.write(f"\t{toWatch}\n")    
    
    def getRoutingTable(self) -> List[str]:
        """Read routing table to list
        """
        rt_entries: List[str] = []
        rt: TextIOWrapper = open("/etc/iproute2/rt_tables", "r")
        for i, line in enumerate(rt):
            if len(line) > 0:
                rt_entries.append(line.strip("\n"))
            sys.stdout.write("Skipping empty line in rt_tables!\n")
        rt.close()
        return rt_entries
    
    def removeDruTableEntries(self) -> None:
        """Removes DRU created routing table entries
        """    
        escapedTableName = re.escape(self.tableName)
        directTable = re.compile(r"(?<!\d)\s+{}[0-9]+(?!\w)".format(escapedTableName), re.IGNORECASE)
                
        sys.stdout.write("Removing old tables..\n")
        updatedTables: List[str] = []
        for line in self.getRoutingTable():
            if directTable.search(line) == None:
                updatedTables.append(line)
        
        rewrite = open("/etc/iproute2/rt_tables", "w")
        for entry in updatedTables:
            rewrite.write("{}\n".format(entry))
        rewrite.close()
               
    def addDruTableEntries(self) -> None:
        """
        """
        self.removeDruTableEntries()
        acceptableTableIds = list(range(0, 255))
        activeTablesCheck = re.compile(r"^(?!#)[0-9]+")
        for line in self.getRoutingTable():
            activeIds = activeTablesCheck.findall(line)
            if len(activeIds) > 0:
                activeId = int(activeIds[0])
                if (activeId in acceptableTableIds):
                    acceptableTableIds.remove(activeId)
        
        appendableTables: List[str] = []
        for i, adapter in enumerate(self.nics):
            tableId = acceptableTableIds.pop(0)
            ntableName: str = "{}{}".format(self.tableName, i)
            tableEntry: str = "{}\t{}".format(tableId, ntableName)
            appendableTables.append(tableEntry)
            self.configuredTables[adapter] = ntableName
        sys.stdout.write("Creating new tables\n")
        with open("/etc/iproute2/rt_tables", "a") as file:
            for table in appendableTables:
                file.write("{}\n".format(table))
                sys.stdout.write(f"{table}\n")
                
    def start(self) -> None:
        """
        """
        sys.stdout.write("Updating and preparing Routing Table entries\n")
        self.addDruTableEntries()
        
        if len(self.nics) == 0 or len(self.configuredTables) == 0:
            sys.stderr.write("Configuration is missing network adapters or configured tables..\n")
            return
        
        sys.stdout.write("Starting DIPWA\n")
        self.dipwa = _DynamicIpWatcherAction(self.nics, self.configuredTables)
        self.dipwa.start()
        
    def stop(self) -> None:
        self.dipwa.stop()
        self.removeDruTableEntries()
        sys.stdout.write("Stopped DIPWA and removed created Routing Table entries\n")