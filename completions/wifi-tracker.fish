# fish completion for wifi-tracker
# Fully dynamic: delegates every completion to the CLI's --complete engine
# so commands/flags/args never go stale when the CLI changes.
complete -c wifi-tracker -e

function __wifi_tracker_complete
    set -l cmd (commandline -opc)
    set -l cword (commandline -ct)
    set -l words (string join " " -- $cmd $cword)
    env COMP_WORDS="$words" wifi-tracker --complete fish "$cword" 2>/dev/null
end

complete -c wifi-tracker -f -a '(__wifi_tracker_complete)'
