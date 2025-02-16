// this code handles search, sort and filter in front end for products

document.addEventListener('DOMContentLoaded', () => {
    const productsMainContainer = document.querySelector('.list-grid-wrapper')
    const totalFound = document.getElementById('total-found')
    const pageBtns = document.querySelector('.pagination')
    const minPriceInput = document.querySelector('.min-price-input')
    const maxPriceInput = document.querySelector('.max-price-input')
    const headerRangeEnd = document.getElementById('header-range-end')
    const mainUrl = document.location.href;
    const sortSelector = document.querySelector('.sort-selector')
    var paginationBtns = document.querySelectorAll('.pagination-button')

    var queryOptions = {};
    function fetchAndInsert(queryOptions) {
        // function only for sending request and inserting the result html
        csrftoken = getCookie("csrftoken");
        var options = {
            method: "POST",
            mode: 'same-origin',
            body: JSON.stringify({ "options": queryOptions }),
            headers: { 'X-CSRFToken': csrftoken, "Content-Type": 'application/json' },
        }

        fetch(mainUrl, options).then(response => response.json()).then(data => {
            totalFound.innerHTML = ``
            totalFound.innerText = data.total_found;

            // updating and setting events to pagination buttons since changing in every query
            pageBtns.innerHTML = `<li class="page-item"><a class="page-link h-64 w-64 flex items-center justify-center text-xxl rounded-8 font-[500] text-neutral-600 border border-gray-100" href="index.html"><i class="ph-bold ph-arrow-left"></i></a></li>`
            for (i = 1; i <= data.total_pages; i++) {
                pageBtns.insertAdjacentHTML("beforeend", `<li class="page-item active"><button class="pagination-button h-64 w-64 flex items-center justify-center text-md rounded-8 font-[500] text-neutral-600 border border-gray-100" data-page="${i}">${i}</button></li>`
                )
                paginationBtns = document.querySelectorAll('.pagination-button')
                // activating filter by page for new page buttons created
                genericElementsHandler(paginationBtns, "page")
            }
            // handling page x of y results
            if (data.total_found < 6) {
                headerRangeEnd.innerText = data.total_found;
            }
            // inserting products to products container
            productsMainContainer.innerHTML = "";
            productsMainContainer.insertAdjacentHTML("beforeend", data.html)
            // handling add to cart button for all new product elements
            addToCartBtnsEvent()
        })
    }
    // this is a gen-eric function for setting onclick event and calling fetchAndInsert()
    function genericElementsHandler(btn_objs, type) {
        if (type == "price" || type == "sort") {
            // since we have only one price button, we avoid forEach funciton does not exist error
            btn_objs = [btn_objs]
        }


        // sorting 
        if (type == "sort") {
            sortSelector.addEventListener('change', () => {
                queryOptions[type] = sortSelector.value;
                fetchAndInsert(queryOptions);
            })
        }
        // filtering
        else {
            btn_objs.forEach(btn => {
                btn.onclick = () => {
                    queryOptions[type] = btn.dataset[type]
                    if (type == "price") {
                        // since price has got min and max for its range
                        queryOptions[type] = [minPriceInput.value, maxPriceInput.value]
                    }
                    fetchAndInsert(queryOptions);
                }
            })
        }

    }

    // pagination buttons initially, since changing we 
    genericElementsHandler(paginationBtns, "page")
    // category filtering
    const categoryBtns = document.querySelectorAll('.category-btn')
    genericElementsHandler(categoryBtns, "category");
    // price filtering
    const priceFilterBtn = document.querySelector('.price-filter-btn')
    genericElementsHandler(priceFilterBtn, "price")

    // sorting button
    genericElementsHandler(sortSelector, "sort")

})