function addToCartBtnsEvent() {
    // this function enables add-to-cart buttons
    const cartBtns = document.querySelectorAll(".add-to-cart");
    if (cartBtns) {
        cartBtns.forEach(btn => {
            btn.onclick = ((event) => {
                const url = btn.dataset["addtocarturl"];
                fetch(url).then(response => response.json()).then(res => {
                    if (res.OK == 1) {
                        // updating cart badge since new item is added
                        const badges = document.querySelectorAll(".shopping-cart-badge");
                        badges.forEach(span => {
                            span.innerText = parseInt(span.innerText) + 1;
                            swal("اضافه شد", "مورد به سبد خرید اضافه شد", "success")
                        })
                    }
                    else {
                        swal("موجود است", "این مورد  در سبد خرید شما موجود است", "info")

                    }
                })
            })

        })
    }
}
document.addEventListener("DOMContentLoaded", (e) => {

    // handling add to cart initially
    addToCartBtnsEvent()
    // handling deleting cart item
    const deleteBtns = document.querySelectorAll(".delete-cart-item");
    if (deleteBtns) {

        deleteBtns.forEach(btn => {
            btn.onclick = ((event) => {
                const url = btn.dataset["deletecartitemurl"];
                fetch(url).then(response => response.json()).then(res => {
                    if (res.OK == 1) {
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
    const url = document.getElementById("edit_url").innerText.trim();
    if (saveChangesBtn) {
        saveChangesBtn.onclick = ((event) => {
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
            fetch(url, options).then(response => response.text()).then(text => {
                window.location.reload()

            })

        })
    }
})