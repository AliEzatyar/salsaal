function addToCartBtnsEvent() {
    // this function enables add-to-cart buttons
    const cartBtns = document.querySelectorAll(".add-to-cart");
    if (cartBtns) {
        cartBtns.forEach(btn => {
            btn.onclick = ((event) => {
                const url = btn.dataset["addtocarturl"];
                fetch(url).then(response => response.json()).then(res => {
                    if (res.saved == true) {
                        // updating cart badge since new item is added
                        const badges = document.querySelectorAll(".shopping-cart-badge");
                        badges.forEach(span => {
                            span.innerText = parseInt(span.innerText) + 1;
                            swal("اضافه شد", "مورد به سبد خرید اضافه شد", "success")
                        })
                    }
                    else if (res.saved != true && res.error == "exists_before") {
                        swal("موجود است", "این مورد  در سبد خرید شما موجود است", "info")

                    }
                    else if (res.saved != true && res.error == "no_existing") {
                        swal("باقی مانده صفر", "این مورد فعلا موجود نیست", "info")

                    }
                })
            })

        })
    }
}
document.addEventListener("DOMContentLoaded", (e) => {
    // handling add to cart initially
    addToCartBtnsEvent()

    // total price elements
    const totalPrice = document.querySelectorAll(".products-total-price")

    // handling deleting cart item
    const deleteBtns = document.querySelectorAll(".delete-cart-item");
    if (deleteBtns) {

        deleteBtns.forEach(btn => {
            btn.onclick = ((event) => {
                const url = btn.dataset["deletecartitemurl"];
                fetch(url).then(response => response.json()).then(res => {
                    if (res.saved) {
                        // updating total price
                        totalPrice.forEach(el => {
                            el.innerText = res.products_total_price
                        })
                        // updating cart badge since an item is deleted
                        const badges = document.querySelectorAll(".shopping-cart-badge");
                        badges.forEach(span => {
                            span.innerText = parseInt(span.innerText) - 1;
                            swal("حذف شد", "مورد از سبد خرید حذف شد", "success")
                        })
                    }
                })
            })

        })
    }

    // handling items quantity update
    const saveChangesBtn = document.getElementById("save-changes-btn");
    var url = document.getElementById("edit_url")
    if (url) {
        url = url.innerText.trim();
    }
    if (saveChangesBtn) {
        saveChangesBtn.onclick = ((event) => {
            // input elements
            const itemsQuantitiyInputs = document.querySelectorAll(".item-quantity-input");
            var data = new Array()
            itemsQuantitiyInputs.forEach(input => {
                const value = input.value;
                const itemId = input.dataset["itemid"]
                data.push([itemId, value]);

            })
            
            // fetch 
            var options = {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                body: JSON.stringify({
                    items: data,
                }),
            };
            fetch(url, options).then(response => response.json()).then(data => {
                // response
                console.log('response came ......')
                if (data.saved){
                    totalPrice.forEach(el =>{
                        console.log(el)
                        el.innerText = data.products_total_price
                    })
                    swal("ثبت شد", "تغییرات در سبد خرید موفقانه ثبت شد.", "success")
                }
                else{
                    swal("مشکلی پیش آمد", "ثبت تغییرات در سبد خرید ناموفق بود.", "info")

                }
            })

        })
    }
})