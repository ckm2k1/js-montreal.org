function Data(props) {
    const {
        socket,
        jobs: {
            pending = [],
            submitted = [],
            acked = [],
            succeeded = [],
            failed = [],
            cancelled = []
        } = {},
        queue = 0,
        total = 0
    } = props;

    const [stats, setState] = React.useState({
        jobs: {
            pending: pending,
            submitted: submitted,
            acked: acked,
            succeeded: succeeded,
            failed: failed,
            cancelled: cancelled
        },
        queue: queue,
        total: total
    });

    function handleUpdate(event) {
        console.log("DATA", event.data);
        setState(JSON.parse(event.data));
    }

    React.useEffect(() => {
        socket.addEventListener("message", handleUpdate);

        return () => {
            socket.removeEventListener("message", handleUpdate);
        };
    });

    return (
        <React.Fragment>
            <table className="overview-table">
                <thead>
                    <tr>
                        <th>Pending</th>
                        <th>Submitted</th>
                        <th>Acked</th>
                        <th>Succeeded</th>
                        <th>Failed</th>
                        <th>Cancelled</th>
                        <th>Action Queue</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td className="data pending">
                            {stats.jobs.pending.length}
                        </td>
                        <td className="data submitted">
                            {stats.jobs.submitted.length}
                        </td>
                        <td className="data acked">
                            {stats.jobs.acked.length}
                        </td>
                        <td className="data succeeded">
                            {stats.jobs.succeeded.length}
                        </td>
                        <td className="data failed">
                            {stats.jobs.failed.length}
                        </td>
                        <td className="data cancelled">
                            {stats.jobs.cancelled.length}
                        </td>
                        <td className="data queue">{stats.queue}</td>
                        <td className="data total">{stats.total}</td>
                    </tr>
                </tbody>
            </table>

            <JobTable jobs={Object.values(stats.jobs).flat()} name={"Jobs"} />
        </React.Fragment>
    );
}

function fmtDate(ts) {
    return new Date(ts * 1000).toLocaleString();
}

function jobStateToCss(state) {
    state = state.toLowerCase();
    switch (state) {
        case "queuing":
        case "queued":
        case "running":
        case "cancelling":
            return "acked";
        default:
            return state;
    }
}

function JobTableCell(props) {
    return (
        <tr>
            <td>{props.index}</td>
            <td>
                <a target="_blank" href={`/jobs/${props.jid}`}>
                    {props.jid}
                </a>
            </td>
            <td className={jobStateToCss(props.state)}>{props.state}</td>
            <td>{fmtDate(props.created)}</td>
            <td>{props.updated && fmtDate(props.updated)}</td>
            <td>{props.spec.name}</td>
            <td>
                <code>
                    {props.spec.command &&
                        props.spec.command.join(" ").slice(0, 50)}
                </code>
            </td>
        </tr>
    );
}

function JobTable(props) {
    const { jobs = [], name } = props;

    return (
        <table className="overview-table">
            <caption>{name[0].toUpperCase() + name.slice(1)}</caption>
            <thead>
                <tr>
                    <th>Index</th>
                    <th>Job Id</th>
                    <th>State</th>
                    <th>Created</th>
                    <th>Updated</th>
                    <th>Name</th>
                    <th>Command</th>
                </tr>
            </thead>
            <tbody>
                {jobs.map(job => {
                    return <JobTableCell key={job.index} {...job} />;
                })}
            </tbody>
        </table>
    );
}

// Create WebSocket connection.
const proto = window.location.protocol === "https" ? "wss" : "ws";
window.socket = new WebSocket(`${proto}://${window.location.host}/ws`);
// Connection opened
socket.addEventListener("open", function(event) {
    socket.send("Connected to PA server.");
});

// Disconnect handler.
socket.addEventListener("close", function(event) {
    console.log("Process agent disconnected!");
});

console.log("OH YEAH");
const domContainer = document.querySelector(".data");
ReactDOM.render(<Data socket={socket} />, domContainer);