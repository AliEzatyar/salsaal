// handling sending and handling fetch requests for pagination and searching and filtering

document.addEventListener('DOMContentLoaded', () => {
    const productsMainContainer = document.querySelector('.list-grid-wrapper')
    const totalFound = document.getElementById('total-found')
    const pageBtns = document.querySelector('.pagination')
    const minPriceInput = document.querySelector('.min-price-input')
    const maxPriceInput = document.querySelector('.max-price-input')
    const headerRangeEnd = document.getElementById('header-range-end')
    const mainUrl = document.location.href;

    var varUrlDict = {};

    // this is a gen-eric function for setting onclick event and fetching and inserting the result html to products container
    function fetchHandler(btn_objs, type) {
        if (type == "price") {
            btn_objs = [btn_objs]
        }

        btn_objs.forEach(btn => {
            btn.onclick = () => {
                varUrlDict[type] = btn.dataset[type]
                if (type == "price") {
                    varUrlDict[type] = [minPriceInput.value, maxPriceInput.value]
                }
                csrftoken = getCookie("csrftoken");
                var options = {
                    method: "POST",
                    mode: 'same-origin',
                    body: JSON.stringify({ "options": varUrlDict }),
                    headers: { 'X-CSRFToken': csrftoken, "Content-Type": 'application/json' },
                }

                fetch(mainUrl, options).then(response => response.json()).then(data => {
                    totalFound.innerHTML = ``
                    totalFound.innerText = data.total_found;

                    pageBtns.innerHTML = `<li class="page-item"><a class="page-link h-64 w-64 flex items-center justify-center text-xxl rounded-8 font-[500] text-neutral-600 border border-gray-100" href="index.html"><i class="ph-bold ph-arrow-left"></i></a></li>`
                    for (i = 1; i <= data.total_pages; i++) {
                        pageBtns.insertAdjacentHTML("beforeend", `<li class="page-item active"><button class="pagination-button h-64 w-64 flex items-center justify-center text-md rounded-8 font-[500] text-neutral-600 border border-gray-100" data-page="${i}">${i}</button></li>`
                        )
                    }
                    if (data.total_found < 6) {
                        headerRangeEnd.innerText = data.total_found;
                    }
                    productsMainContainer.innerHTML = "";
                    productsMainContainer.insertAdjacentHTML("beforeend", data.html)
                })
            }
        })
    }

    // pagination button
    const paginationBtns = document.querySelectorAll('.pagination-button')
    fetchHandler(paginationBtns, "page")
    // category filtering
    const categoryBtns = document.querySelectorAll('.category-btn')
    fetchHandler(categoryBtns, "category");
    // price filtering
    const priceFilterBtn = document.querySelector('.price-filter-btn')
    fetchHandler(priceFilterBtn, "price")


})