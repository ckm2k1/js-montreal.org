for i in (seq 0 9);
    curl -X PUT \
        -d '[{"environmentVars": ["EAI_PROCESS_AGENT_INDEX='$i'"], "state": "RUNNING", "id": "'(uuidgen | string lower)'"}]' \
        -H 'content-type: application/json' localhost:8666/v1/jobs;
    sleep .1;
end;

curl -X PUT -d '[{"environmentVars": ["EAI_PROCESS_AGENT_INDEX=0"], "state": "RUNNING", "id": "'(uuidgen | string lower)'"}]' \ -H 'content-type: application/json' localhost:8666/v1/jobs;