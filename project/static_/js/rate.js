/*
    This code makes rating ajax
*/
document.addEventListener('DOMContentLoaded', ()=>{
    const btn = document.getElementById('submit')
    const rateUrl = window.location.protocol +"//" +window.location.host + document.getElementById('rate_url').innerText
    btn.onclick = ()=>{
        const form = document.getElementById('rate-form')
        const formObj = new FormData(form) 
        const formEntries = Object.fromEntries(formObj.entries());
        const csrftoken = getCookie("csrftoken");
        
        var options = {
            method: "POST",
            mode: 'same-origin',
            body: JSON.stringify({ "options": formEntries }),
            headers: { 'X-CSRFToken': csrftoken, "Content-Type": 'application/json' },
        }
        fetch(rateUrl,options).then(response => response.json()).then(json =>{
            if (json.OK){
                swal("","نظر شما ثبت شد","success")
            }
        })
    }
})