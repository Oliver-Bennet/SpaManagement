function onServiceChange() {
    const serviceSelect = document.getElementById("service_id");
    const duration = serviceSelect.selectedOptions[0].dataset.duration;

    const start = document.getElementById("start_time").value;
    if (!start || !duration) return;

    const [h, m] = start.split(":").map(Number);
    const end = new Date(0, 0, 0, h, m + parseInt(duration));

    document.getElementById("end_time").value =
        end.toTimeString().slice(0, 5);