/*
    this code handles cancelation of an order by customer
*/

document.addEventListener('DOMContentLoaded', () => {
    const cancelBtns = document.querySelectorAll('.cancel-order')
    var cancelOrderUrl = document.getElementById('cancel-order-url')
    if (cancelOrderUrl) {
        cancelOrderUrl = cancelOrderUrl.innerText.trim()
    }
    cancelBtns.forEach(btn => {
        btn.onclick = (e) => {
            // getting the id of order
            const orderId = btn.dataset['id']

            // request headers
            var options = {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                body: JSON.stringify({
                    id: orderId,
                }),
            };
            // fetch
            fetch(cancelOrderUrl, options).then(response => response.json()).then(data => {
                if (data.saved) {
                    swal("لغو شد", "سفارش شما موفقانه لغو شد.", "success")

                }
                else{
                    swal("خطا", "در جریان حذف سفارش شما مشکلی بوجود آمد.", "info")

                }
            })
        }
    })
})