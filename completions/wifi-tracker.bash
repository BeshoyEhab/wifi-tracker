# bash completion for wifi-tracker

_wifi_tracker_completions() {
    local cur prev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    local suggestions
    suggestions=$(COMP_WORDS="${COMP_WORDS[*]}" COMP_CWORD=$COMP_CWORD wifi-tracker --complete bash "$cur" 2>/dev/null)

    if [[ -n "$suggestions" ]]; then
        COMPREPLY=($(compgen -W "$suggestions" -- "$cur"))
    fi
    return 0
}

complete -F _wifi_tracker_completions wifi-tracker
