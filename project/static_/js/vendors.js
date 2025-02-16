// this code handles search, sort and filter in front end for vendors

document.addEventListener('DOMContentLoaded', () => {
    const vendorsMainContainer = document.querySelector('.list-grid-wrapper')
    const totalFound = document.getElementById('total-found')
    const pageBtnsUl = document.querySelector('.pagination')
    const mainUrl = document.location.href;
    const filterCity = document.getElementById("filter-city-selector")
    const categoryBtns = document.querySelectorAll('.category-btn')

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
            pageBtnsUl.innerHTML = `<li class="page-item"><a class="page-link h-64 w-64 flex items-center justify-center text-xxl rounded-8 font-[500] text-neutral-600 border border-gray-100" href="index.html"><i class="ph-bold ph-arrow-left"></i></a></li>`
            for (i = 1; i <= data.total_pages; i++) {
                pageBtnsUl.insertAdjacentHTML("beforeend", `<li class="page-item active"><button class="pagination-button h-64 w-64 flex items-center justify-center text-md rounded-8 font-[500] text-neutral-600 border border-gray-100" data-page="${i}">${i}</button></li>`
                )
                paginationBtns = document.querySelectorAll('.pagination-button')
                // activating filter by page for new page buttons created
                genericElementsHandler(paginationBtns, "page")
            }
            // inserting products to products container
            vendorsMainContainer.innerHTML = "";
            vendorsMainContainer.insertAdjacentHTML("beforeend", data.html)

        })
    }
    // this is a gen-eric function for setting onclick event and calling fetchAndInsert()
    function genericElementsHandler(btn_objs, type) {
        if (type == "city") {
            console.log("setting city")
            // filtering by city is different
            filterCity.addEventListener('change', (e) => {
                console.log("ciyt")
                queryOptions[type] = filterCity.value;
                fetchAndInsert(queryOptions);
            })
            }
        // filtering by other parameters like category, rating, page
        else {
            btn_objs.forEach(btn => {
                btn.onclick = () => {
                    btn.classList.add("bg-green-500")

                    queryOptions[type] = btn.dataset[type]
                    fetchAndInsert(queryOptions);
                }
            })
        }

    }

    // pagination buttons initially, since changing we
    genericElementsHandler(paginationBtns, "page")
    // category filtering
    genericElementsHandler(categoryBtns, "category");
    // city filtering button
    genericElementsHandler(filterCity, "city")

})