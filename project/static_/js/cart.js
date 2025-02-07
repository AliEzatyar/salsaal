document.addEventListener("DOMContentLoaded", (e) => {
    const cartBtns = document.querySelectorAll(".add-to-cart");
    cartBtns.forEach(btn => {
        btn.onclick = ((event) => {
            const url = btn.dataset["addtocarturl"];
            fetch(url)
        })

    })
    const deleteBtns = document.querySelectorAll(".delete-cart-item");
    deleteBtns.forEach(btn => {
        btn.onclick = ((event) => {
            const url = btn.dataset["deletecartitemurl"];
            fetch(url);
        })

    })
    // handling items quantity update
    const saveChangesBtn = document.getElementById("save-changes-btn");
    const url = document.getElementById("edit_url").innerText.trim();
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
        fetch(url,options).then(response => response.text()).then(text=>{
            window.location.reload()

        })

    })

})