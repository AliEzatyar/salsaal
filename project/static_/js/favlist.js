/*
    This code manages fav list:
    * item addition to fav list
    * item deletion from fav list
*/
document.addEventListener("DOMContentLoaded", (e) => {
    // automating add to fav list by setting event controller on buttons
    const addToFavBtn = document.getElementById("add-to-favlist");
    if (addToFavBtn) {
        addToFavBtn.onclick = ((event) => {
            const url = addToFavBtn.dataset["addtofavlisturl"];
            fetch(url).then(response => response.json()).then(res => {
                if (res.OK == 1) {
                    // updating cart badge since new item is added
                    const badges = document.querySelectorAll(".favlist-badge");
                    badges.forEach(span => {
                        span.innerText = parseInt(span.innerText) + 1;
                        swal("اضافه شد", "مورد به لیست علاقه اضافه شد", "success")
                    })
                }
            })
        })
    }

    // handling deleting cart item
    const deleteBtns = document.querySelectorAll(".delete-fav-item");
    deleteBtns.forEach(btn => {
        btn.onclick = ((event) => {
            const url = btn.dataset["deletefavitemurl"];
            fetch(url).then(response => response.json()).then(res => {

                if (res.OK == 1) {
                    // updating cart badge since an item is deleted
                    const badges = document.querySelectorAll(".favlist-badge");
                    badges.forEach(span => {
                        span.innerText = parseInt(span.innerText) - 1;
                        swal("حذف شد", "مورد از لیست علاقه حذف شد", "success")
                    })
                }
            })
        })

    })

})
