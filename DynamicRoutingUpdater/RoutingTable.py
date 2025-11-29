import sys, os, re
from typing import List
import logging

logging.basicConfig(level=logging.INFO)

def operationOut(command: str = None) -> None:
    result = os.system(command)
    if result != 0:
        logging.error(f"{command}\n\tResult: {result}")
    else:
        logging.info(f"{command}")

class RoutingTable:
    """"""
    rt_table_file = "/etc/iproute2/rt_tables"
    
    tableBaseName: str = None
    adapterNames: List[str] = []
    
    def __init__(self, tableBaseName: str = None, adapterNames: List[str] = []) -> None:
        if (tableBaseName is None):
            raise ValueError(f"tableBaseName is {tableBaseName}, None is not supported!")
        self.tableBaseName = tableBaseName
        if (len(adapterNames) == 0):
            raise ValueError(f"adapterNames is {adapterNames}, Empty is not supported!")
        self.adapterNames = adapterNames
        
    
    
    @staticmethod
    def getRoutingTables() -> List[str]:
        """Read routing table to list
        """
        rt_entries: List[str] = []
        
        with open(RoutingTable.rt_table_file, "r") as rt_tables:
            for line in rt_tables:
                if len(line.strip("\t\r\n")) > 0:
                    rt_entries.append(line.strip("\n"))
                else:
                    logging.info("Skipping empty line in rt_tables!")
        return rt_entries
    
    def deleteMyEntries(self) -> None:
        """Removes DRU created routing table entries
        """    
        escapedTableName = re.escape(self.tableBaseName)
        directTable = re.compile(r"[0-9]+\t{}[0-9]+(?!\w)".format(escapedTableName), re.IGNORECASE)
                
        logging.info("Removing old tables..")
        updatedTables: List[str] = []
        for line in RoutingTable.getRoutingTables():
            if directTable.search(line) == None:
                updatedTables.append(line)
        
        rewrite = open(self.rt_table_file, "w")
        for entry in updatedTables:
            rewrite.write("{}\n".format(entry))
        rewrite.close()
        
    def addMyEntries(self) -> dict:
        """
        """
        configuredTables: dict = {}
        self.deleteMyEntries()
        acceptableTableIds = list(range(100, 255))
        activeTablesCheck = re.compile(r"^(?!#)[0-9]+")
        for line in RoutingTable.getRoutingTables():
            activeIds = activeTablesCheck.findall(line)
            if len(activeIds) > 0:
                activeId = int(activeIds[0])
                if (activeId in acceptableTableIds):
                    acceptableTableIds.remove(activeId)
        
        appendableTables: List[str] = []
        for i, adapter in enumerate(self.adapterNames):
            tableId = acceptableTableIds.pop(0)
            ntableName: str = "{}{}".format(self.tableBaseName, i)
            tableEntry: str = "{}\t{}".format(tableId, ntableName)
            appendableTables.append(tableEntry)
            configuredTables[adapter] = ntableName
        logging.info("Creating new tables")
        with open(self.rt_table_file, "a") as file:
            for table in appendableTables:
                file.write("{}\n".format(table))
                logging.info(f"{table}")
        return configuredTables
        
