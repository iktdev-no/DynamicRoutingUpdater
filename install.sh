#! /bin/bash

echo -e "\033[1;35m
                ....'.. .'''....
            ..',,,'.    .,,,,,,,'...
         ..,,,,,,,.     .',,,,,,''''..
       ..,,,,,,,,,.     .',,,,'''''''''.
      .,,,,,,,,,,,.    .',,,''''''''''''..
    .',,,,,,,,,,,'.  .',,,''''''''''''''''.
   .',,,,,,,,,,,'.  .',,'''''''''''''''''''.
   .,,,,,,,,,,,.   .',,'''''''''''....''....
   ..,,,,,,,,'.  .',''''''''''''..
     .',,,,,'.  .''''''''''''''.         .....
 .'.   .,,,'.  .'''''''''.....         .......
  ',..  ...   .'''......      .....  .........
  ....        .         .....''''''...........
              ........'''''''''''.............
   ...        ..'''''''''''''''..............
       ..'''.   ..''''''''''................
      .'''''''.    .....''.................
       .''''''''..      .................
         .'''''''.       ..............
           ...''''.      ............
              ..........    ......
                     ....
\033[0m
"

# Last inn distribusjonsinfo
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
else
    echo "Unsupported distro..."
    exit 1
fi

case $DISTRO in
    ubuntu|debian)
        PACKAGE_MANAGER="apt"
        INSTALL_CMD="apt install -y"
        ;;
    fedora|nobara)
        PACKAGE_MANAGER="dnf"
        INSTALL_CMD="dnf install -y"
        ;;
    *)
        echo "Distro $DISTRO is not supported."
        exit 1
        ;;
esac

echo "Supported distro: $DISTRO. Using package manager $PACKAGE_MANAGER."

get_packages() {
    case $DISTRO in
        ubuntu|debian) echo "python3-pip python3-venv whiptail" ;;
        fedora|nobara) echo "python3-pip python3-venv newt gcc" ;;
    esac
}

prerequisites() {
    # Her henter du listen dynamisk
    local PKGS=$(get_packages)
    
    if [ -z "$PKGS" ]; then
        echo "Kunne ikke finne pakkeliste for $DISTRO."
        exit 1
    fi

    # Installer
    sudo $PACKAGE_MANAGER $PKGS
    mkdir --parents /usr/local/dynamic-routing-updater/
    sudo chmod -R 0777 /usr/local/dynamic-routing-updater/
    python3 -m venv /usr/local/dynamic-routing-updater/venv
    source /usr/local/dynamic-routing-updater/venv/bin/activate

    echo "Installing dependencies"

    # Sett navnet på pakken
    package_name="pyDynamicRoutingUpdater"

    # Sjekk om pakken er installert
    if python -c "import $package_name" &> /dev/null; then
        # Lagre gjeldende versjon
        current_version=$(pip show $package_name | grep Version | awk '{print $2}')
        echo "Gjeldende versjon av $package_name er $current_version"
    else
        echo "$package_name er ikke installert."
    fi

    # Installer eller oppdater pakken
    pip install $package_name -U

    # Sjekk om installasjonen var vellykket
    if [ $? -eq 0 ]; then
        # Sjekk om versjonsnummeret har endret seg
        new_version=$(pip show $package_name | grep Version | awk '{print $2}')
        if [ "$current_version" != "$new_version" ]; then
            echo "$package_name ble oppdatert fra versjon $current_version til $new_version."
        else
            echo "$package_name var allerede på den nyeste versjonen $new_version."
        fi
    else
        echo "Feil under installasjon eller oppdatering av $package_name. Avbryter."
        exit 1
    fi
    deactivate
}



backup() {
    local etc_path="/etc/iproute2/rt_tables"
    local usr_path="/usr/share/iproute2/rt_tables"

    echo "Checking rt_tables status..."

    # Panic if both exist
    if [ -f "$etc_path" ] && [ -f "$usr_path" ]; then
        echo "PANIC: Both /etc/ and /usr/share/ rt_tables exist. Aborting to prevent configuration conflict."
        return 1
    fi

    # Panic if none exist
    if [ ! -f "$etc_path" ] && [ ! -f "$usr_path" ]; then
        echo "PANIC: No rt_tables file found. System configuration missing."
        return 1
    fi

    # Determine which one to back up
    local source
    if [ -f "$etc_path" ]; then
        source="$etc_path"
    else
        source="$usr_path"
    fi

    echo "Found active config at $source. Backing up..."

    if [ -f "${source}.bak" ]; then
        echo "Backup file ${source}.bak already exists. Skipping."
    else
        cp "$source" "${source}.bak" && echo "Backup created successfully at ${source}.bak"
    fi
}


setup() {

    if [ -f "./reference.json" ]; then
        echo "Using existing reference.json"
    else
        default_tablename="direct"
        tableName=$(whiptail --title "Routing table" --inputbox "Please enter a routing table name or keep the preset:" 10 60 "$default_tablename" 3>&1 1>&2 2>&3)

        # Check if the name is empty or equal to "main" or "default"
        if [[ -z "$tableName" || "$tableName" == "main" || "$tableName" == "default" ]]; then
        # Use the default name
            tableName="$default_tablename"
        fi

        # Get a list of all network interfaces that exist on the system
        ifaces=$(ip -o addr show | awk '$3 == "inet" || $3 == "inet6" {print $2,$4}' | sed 's/\/[0-9]*//')

        # Filter out any interfaces that have a local, loopback or private IP
        ifaces=$(echo "$ifaces" | while read iface ip_addr; do
            if [[ $ip_addr =~ ^(127\.|::1|fe80:|169\.254\.|[10]\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.) ]]; then
                continue
            fi
            echo "$iface ($ip_addr) off"
        done)

        selected_adapters=""
        while true; do
            # Use whiptail to display a dialog with the interfaces
            selected_adapters=$(whiptail --title "Select Network Interface" --checklist "Choose interfaces:" 0 0 0 $(echo "$ifaces") 3>&1 1>&2 2>&3)
            exit_status=$?

            if [ $exit_status != 0 ]; then
                # User cancelled out of the dialog
                break
            fi

            # Check if selected_adapters user selected any options
            if [[ -n "$selected_adapters" ]]; then
                # Output the selected options
                break
            else
                # Prompt the user to select at least one option
                whiptail --title "Error" --msgbox "Please select at least one option." 10 60
            fi

        done

        if [ -z "$selected_adapters" ]; then
            echo "No selection made, exiting..."
            return 1
        fi

        echo "Using Routing table name: $tableName"
        echo "Using Network Adapters:"
        for i in $selected_adapters; do
            echo $i
        done

        # Convert selected_adapters into a JSON array
        adapter_array=($(echo "$selected_adapters" | tr '\n' ' '))

        # Generate the JSON output
        json_output=$(printf '{"tableName": "%s", "adapter": [%s]}' "$tableName" "$(printf '%s,' "${adapter_array[@]}" | sed 's/,$//')")

        # Print the JSON output
        echo "$json_output" > reference.json

    fi  

    systemctl stop dynamic-routing-updater.service
    systemctl disable dynamic-routing-updater.service

    rm /etc/systemd/system/dynamic-routing-updater.service
    systemctl daemon-reload

    echo "Creating DRU Service runner"
    cat > /usr/local/dynamic-routing-updater/service.py <<EOL
from DynamicRoutingUpdater import DynamicRoutingUpdater
reference = "reference.json"
service = DynamicRoutingUpdater(reference)
service.start()
EOL

    cp ./reference.json /usr/local/dynamic-routing-updater/reference.json
    referenceAbsPath="/usr/local/dynamic-routing-updater/reference.json"
    sed -i "s^reference.json^$referenceAbsPath^g" /usr/local/dynamic-routing-updater/service.py

    echo "Creating DRUHook"

    echo '
#! /bin/bash

# Dynamic Routing Updater Hook (DRUHook)
# A component of DynamicRoutingUpdater
# 
# The purpose of DRUHook is to be notified by the system when there are changes to net network interface
# If this script is placed correctly inside a hook folder for the network manager, 
# the network manager will call up this script whith the interface that has been updated or altered
#
# This script will then proceed to update a temporary file which the service DRU will watch and respond to
#

IFACE = $1
STATUS = $2


echo "DRU - DynamicIpWatcherAction: Registered change to network adpater $IFACE"

if [ ! -z $IFACE ]; then
    echo -e "$IFACE\n" >> /tmp/dru-hook
fi
' | tee /etc/networkd-dispatcher/routable.d/dru-hook.sh > /usr/lib/networkd-dispatcher/routable.d/dru-hook.sh > /etc/NetworkManager/dispatcher.d/dru-hook.sh 


    echo "Creating DRU Service"
    cat > /etc/systemd/system/dynamic-routing-updater.service <<EOL
[Unit]
Description=Dynamic Routing Updater - Table flipper

[Service]
Type=simple
Restart=always
ExecStart=/usr/local/dynamic-routing-updater/venv/bin/python -u /usr/local/dynamic-routing-updater/service.py
Environment=PYTHONUNBUFFERED=1


[Install]
WantedBy=multi-user.target
EOL
    CHMOD_FILES=(
    "/etc/networkd-dispatcher/routable.d/dru-hook.sh"
    "/usr/lib/networkd-dispatcher/routable.d/dru-hook.sh"
    "/etc/NetworkManager/dispatcher.d/dru-hook.sh"
    "/usr/local/dynamic-routing-updater/service.py"
    )

    for FILE in "${CHMOD_FILES[@]}"; do
        chmod 755 $FILE
        chmod +x $FILE
    done

    chown root:root /usr/local/dynamic-routing-updater/service.py

    systemctl daemon-reload

    systemctl enable dynamic-routing-updater.service
    systemctl start dynamic-routing-updater.service

    systemctl status dynamic-routing-updater.service

    echo "Done!"
 #   journalctl -exfu dynamic-routing-updater
    sudo chmod -R 755 /usr/local/dynamic-routing-updater/

}





backup
prerequisites
setup