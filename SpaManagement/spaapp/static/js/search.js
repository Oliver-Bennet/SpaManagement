
$(document).ready(function() {
        // Kích hoạt Select2 trên thẻ có id="customer_select"
        $('#customer_select').select2({
            placeholder: "-- Gõ tên hoặc SĐT để tìm --",
            allowClear: true,
            width: '100%' // Đảm bảo rộng bằng khung input
        });
    });