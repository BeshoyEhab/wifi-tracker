# fish completion for wifi-tracker
complete -c wifi-tracker -e

function __wifi_tracker_complete
    set -l cmd (commandline -opc)
    set -l cword (commandline -ct)
    set -l words (string join " " -- $cmd $cword)
    env COMP_WORDS="$words" wifi-tracker --complete fish "$cword" 2>/dev/null
end

function __wifi_tracker_seen_subcommand
    set -l cmd (commandline -opc)
    for sub in $argv
        if contains -- $sub $cmd
            return 0
        end
    end
    return 1
end

function __wifi_tracker_range_values
    echo -e "1h\n24h\n7d\n30d\n12m"
end

function __wifi_tracker_networks
    wifi-tracker --complete fish "" 2>/dev/null
end

# Subcommand completions
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a daemon -d 'Start daemon mode'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a watch -d 'Live dashboard'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a status -d 'Show usage stats'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a today -d 'Quick one-liner'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a graph -d 'ASCII usage graph'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a top-apps -d 'Show apps using network'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a networks -d 'Show saved networks'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a limit -d 'Set data limit'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a remove-limit -d 'Remove data limit'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a usage-from -d 'Set usage start date'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a alert -d 'Configure alerts'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a trust-gateway -d 'Trust a gateway'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a trusted-gateways -d 'List trusted gateways'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a mark-safe -d 'Mark app safe'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a safe-apps -d 'List safe apps'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a kill-app -d 'Kill/auto-kill app'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a kill-list -d 'List auto-kill apps'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a stop -d 'Stop daemon'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a cleanup -d 'Clean old data'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a install-service -d 'Install systemd service'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a remove-service -d 'Remove systemd service'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a block-gateway -d 'Block a gateway'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a blocked-gateways -d 'List blocked gateways'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a unblock-gateway -d 'Unblock a gateway'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a untrust-gateway -d 'Remove a trusted gateway'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a d -d 'Start daemon'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a w -d 'Live dashboard'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a s -d 'Show stats'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a t -d 'Quick status'
complete -c wifi-tracker -f -n '__fish_use_subcommand' -a g -d 'Usage graph'

# --range flag values for status, graph, today
complete -c wifi-tracker -f -n '__wifi_tracker_seen_subcommand status graph today' -l range -a '(__wifi_tracker_range_values)' -d 'Time range'
complete -c wifi-tracker -f -n '__wifi_tracker_seen_subcommand status' -l all -d 'Show all networks'
complete -c wifi-tracker -f -n '__wifi_tracker_seen_subcommand status' -l from-date -r -d 'Start date (YYYY-MM-DD)'
complete -c wifi-tracker -f -n '__wifi_tracker_seen_subcommand status' -l to-date -r -d 'End date (YYYY-MM-DD)'
complete -c wifi-tracker -f -n '__wifi_tracker_seen_subcommand graph' -l from-date -r -d 'Start date (YYYY-MM-DD)'
complete -c wifi-tracker -f -n '__wifi_tracker_seen_subcommand graph' -l to-date -r -d 'End date (YYYY-MM-DD)'

# Global flags
complete -c wifi-tracker -f -l interface -s i -r -d 'Network interface'
complete -c wifi-tracker -f -l interval -r -d 'Update interval (seconds)'
complete -c wifi-tracker -f -l quiet -s q -d 'Suppress notifications'
complete -c wifi-tracker -f -l json -s j -d 'JSON output'
complete -c wifi-tracker -f -l version -d 'Show version'

# Dynamic completions for subcommands that need network names, app names, etc.
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from limit' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from remove-limit' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from usage-from' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from mark-safe' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from kill-app' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from trust-gateway' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from block-gateway' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from unblock-gateway' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from untrust-gateway' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from blocked-gateways' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from safe-apps' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from kill-list' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from trusted-gateways' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from graph' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from status' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from alert' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from cleanup' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from today' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from top-apps' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from networks' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from stop' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from install-service' -a '(__wifi_tracker_complete)'
complete -c wifi-tracker -f -n '__fish_seen_subcommand_from remove-service' -a '(__wifi_tracker_complete)'
