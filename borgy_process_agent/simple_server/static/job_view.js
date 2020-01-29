// Create WebSocket connection.
const pageProto = window.location.protcol;
const socketProto = pageProto === "https:" ? "wss:" : "ws:";
const draveurUrl = `${pageProto}//draveur.borgy.elementai.net/v1/jobs/logs`;
const k8sProxy = `${socketProto}//k8s-proxy.borgy.elementai.net/jobs`;

async function getOutput(jid) {
    const res = await window.fetch(`${draveurUrl}/${jid}`);
    if (!res.ok) {
        console.debug(res.status, res.statusText);
        if (res.status === 404) msg = "Job not found";
        if (res.status === 500) msg = "Remote server error";
        throw new Error(`${res.status}: ${msg} ${res.statusText}`);
    }
    return await res.text();
}

function LogLine({ line } = props) {
    return (
        <div className="log-line">
            <pre>{line}</pre>
        </div>
    );
}

function OutputView() {
    const [output, setState] = React.useState("");

    async function getDraveur(jid) {
        let jobLog = [];
        try {
            response = await getOutput(jid);
            jobLog = parseLog(response);
        } catch (err) {
            jobLog = [err.message];
        }
        setState(jobLog);
    }

    async function getSocket(jid) {
        const socket = new WebSocket(`${k8sProxy}/${jid}/logs=follow=1`);

        socket.addEventListener("open", event => {
            console.log("Connected to k8s proxy.");
        });

        socket.addEventListener("close", event => {
            console.log("K8s proxy disconnected.");
        });

        socket.addEventListener("message", async event => {
            const { data } = event;
            const text = await data.text();
            setTimeout(() => {
                setState(output => output + parseLog(text));
            }, 1);
        });

        socket.addEventListener("error", event => {
            console.log(
                "Error fetching from K8S Proxy. Trying Draveur instead."
            );
            getDraveur(jid);
        });
    }

    function parseLog(raw) {
        raw = raw || "";
        return raw.trim();
    }

    React.useEffect(() => {
        if (window.__jid) {
            getSocket(window.__jid);
        }
    }, []);

    return (
        <div className="job-output">
            <pre>{output}</pre>
        </div>
    );
}

function JobView() {
    return (
        <React.Fragment>
            <h4 className="job-title">Job: {window.__jid}</h4>
            <OutputView />
        </React.Fragment>
    );
}

const domContainer = document.querySelector(".data");
ReactDOM.render(<JobView />, domContainer);
