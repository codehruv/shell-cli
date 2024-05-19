#!/bin/zsh

# This ZSH plugin reads the text from the current buffer 
# and uses a Python script to complete the text.

create_completion() {
    # Get the text typed until now.
    text=${BUFFER}
    # Also add the previous 2 commands and their output to the text.
    extra_text=$(fc -l -2 -1 | awk '{print $2}' | tac | xargs -I {} echo -n "{} ") 
    completion=$(echo -n "$aliases\n\n$extra_text\n\n$text" | $CODEX_CLI_PATH/src/codex_query.py)
    # Add completion to the current buffer.
    BUFFER="${text}${completion}"
    # Put the cursor at the end of the line.
    CURSOR=${#BUFFER}
}

# Bind the create_completion function to a key.
zle -N create_completion

setopt interactivecomments
