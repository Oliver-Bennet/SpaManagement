    // 1. Script chặn ngày quá khứ (Code cũ của bạn + logic mới)
    const dateInput = document.getElementById("booking-date");
    const errorText = document.getElementById("date-error");
    const timeSelect = document.getElementById("time-select");

    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    const todayStr = `${yyyy}-${mm}-${dd}`;

    dateInput.min = todayStr;

    // 2. Hàm xử lý ẩn giờ đã qua
    function updateTimeSlots() {
        const selectedDate = dateInput.value;
        const now = new Date();
        const currentH = now.getHours();
        const currentM = now.getMinutes();

        // Lấy tất cả các option trong thẻ select giờ
        const options = timeSelect.options;

        for (let i = 0; i < options.length; i++) {
            const opt = options[i];
            const timeVal = opt.value; // Ví dụ: "09:30"

            if (!timeVal) continue; // Bỏ qua dòng "-- Chọn giờ --"

            // Tách giờ phút
            const [h, m] = timeVal.split(":").map(Number);

            // Logic kiểm tra
            if (selectedDate === todayStr) {
                // Nếu là hôm nay, so sánh với giờ hiện tại
                // Nếu giờ nhỏ hơn HOẶC (giờ bằng nhau nhưng phút nhỏ hơn) -> Disable
                if (h < currentH || (h === currentH && m <= currentM)) {
                    opt.disabled = true;
                    opt.style.color = "#ccc"; // Làm mờ đi
                    opt.text = timeVal + " (Đã qua)";
                } else {
                    opt.disabled = false;
                    opt.style.color = "";
                    opt.text = timeVal; // Trả lại text gốc
                }
            } else {
                // Nếu là ngày tương lai, mở lại tất cả
                opt.disabled = false;
                opt.style.color = "";
                // Xóa chữ (Đã qua) nếu có
                opt.text = timeVal.replace(" (Đã qua)", "");
            }
        }

        // Reset lựa chọn nếu option đang chọn bị disabled
        if (timeSelect.selectedOptions[0].disabled) {
            timeSelect.value = "";
        }
    }

    dateInput.addEventListener("change", function () {
        if (this.value < todayStr && this.value !== "") {
            errorText.classList.remove("d-none");
            this.value = "";
        } else {
            errorText.classList.add("d-none");
            // Gọi hàm cập nhật giờ khi đổi ngày
            updateTimeSlots();
        }
    });

    // Gọi 1 lần khi trang vừa load (để xử lý trường hợp user F5 hoặc browser tự điền ngày)
    document.addEventListener("DOMContentLoaded", function() {
        if(dateInput.value) {
            updateTimeSlots();
        }
    });