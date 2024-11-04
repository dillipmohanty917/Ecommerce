checkboxes = document.querySelectorAll('input[type=checkbox].checkit')
alert(checkboxes);
 checkboxes.forEach(checkbox => {
  $(checkbox).popover({
    html: true, 
      placement: "left",
      trigger: "click",
      content: function() {
        var av = `${this.id}`;
        av = av.split("-");
        qs = "#popover-content-edit-"+av[1];
        var qString =qs
        return $(qString).html();
      }
  }).on('shown.bs.popover', function () {
      var $popup = $(this);
      populate_data(this);
      $('.edits #saveEdits').on('click',function(){
        $popup.popover('hide');
        var stock_id = $(this).attr('data-id');
      
        // $('input[type=checkbox].inventory-item-update');

		var issue_checkbox = $('input[type=checkbox].issue_checkboxes');
		lists = []
		issue_checkbox.each(function(){
			var $this = $(this);
    		if($this.is(":checked")){
    			$('#'+$this.attr('id')+'-qty').attr('required','true');
    			$('#'+$this.attr('id')+'-comment').attr('required','true');
    			var qnt = $('#'+$this.attr('id')+'-qty').val();
    			var comment = $('#'+$this.attr('id')+'-comment').val();
    			lists.push({"Reason": $this.attr('id').split('-')[0],
    				'quantity': qnt,
    				'comment': comment
    			 })

    			
    			var att_id = $this.attr('id');
    		}
		});
		console.log(JSON.stringify(lists));
		// verify_all(JSON.stringify(lists))
		// console.log($(this).attr('id'))
		$(this).attr('data-id', lists);
		$('#'+$popup.attr('id')).attr('data-val',JSON.stringify(lists));
		// alert('sdjfihsdbf')
		// alert($popup.attr('id'))

      })

      $('.edits #cancelEdits').on('click',function(){
        $popup.popover('hide');
        $popup.prop('checked',false);
      })		
    });
});

function check_hub_stock(){

}

function check_system_stock(){


}
 

function populate_data(prod){
	alert('dsfbsdfjb')
	var jsondata = $(prod).attr('data-issue');
	jsondata = jsondata.replace(/u'/g,'"').replace(/'/g,'"');
	jsondata = JSON.parse(jsondata)
	for(var x = 0; x<jsondata.length;x++){
		var reason = jsondata[x]['Reason'];
		id = $(prod).attr('id').split('-')[1]
		$('#'+reason+'-item-'+id).attr('checked',true);
		alert(('#'+reason+'-item-'+id))
		$('#'+reason+'-item-'+id+'-comment').attr('value',jsondata[x]['comment']);
		$('#'+reason+'-item-'+id+'-qty').attr('value',jsondata[x]['quantity']);
	}

}
// function verify_all(lists){
// 	alert("ebtered");
// 	var extra_items = 0;
// 	var issue_items = 0;
// 	for (var i = lists - 1; i >= 0; i--) {
// 		alert(lists[i]);
// 		alert(lists['Reason'])
// 		if(lists[i]['Reason'] == "extra"){
// 			extra_items=extra_items+lists[i][quantity]
// 		}
// 		else{
// 			issue_items = issue_items + lists[i][quantity];

// 		}
// 	}
// 	alert(extra_items);
// 	alert(issue_items);
// 	if (extra_items){
// 		var hub = check_hub_stock(extra_items);

// 		alert($("#quantity-"+$(this).attr('id')).attr("data-id")); 
// 	}

// }
$('.qty-class').on('input',function(){
	var get_id = $(this).attr('id').split('-');
	$('#edited-'+get_id[1]).removeAttr('disabled');
	$('#inventory-update-'+get_id[1]).removeAttr('disabled');
})


$('.inventory-update').on('click',function(){
	var change_list = []
	id = $(this).attr('id').split('-')[2]
	actual_stock = $('#quantity-'+id).val()
	payload = $('#edited-'+id).attr('data-val')
	stock_json = {
		"id":id,
		"actual_stock":actual_stock,
		"payload":payload
	}
	change_list.push(stock_json)
		if(typeof payload !== "undefined"){
			if( payload !== "[]"){
				$.ajax({
					type:'post',
					url:"{% url 'hub:inventory-list' %}",
					data:{csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value, "response_data": JSON.stringify(change_list) },
					success:(response) =>{
						location.reload();
					},
					error:(error) => {
						alert(error);
						location.reload();

						console.log("error check");
					}
				});
			}
			else
			{
				alert('Issue needs to be mentioned and checked when doing a stock update');
				location.reload();
			}
		}
		else{
			alert('Issue needs to be checked when doing a stock update');
			location.reload();
		}
})

$('#inventory_update_all').on('click',function(){
	var issue_checkbox = $('input[type=checkbox].checkit');
	var stock_objs = []
	var flag = 1;
	issue_checkbox.each(function(){
		var $this = $(this);
		if($this.is(":checked")){
			if($('#edited-'+id).attr('data-val') != "[]"){
			var id = $(this).attr('id').split('-')[1]
			obj = {
				"id":id,
				"actual_stock":$('#quantity-'+id).val(),
				"payload":$('#edited-'+id).attr('data-val')
			}
			stock_objs.push(obj)
		}
	}
	else{
		flag=0
	}
	});
	if (flag){
	    $.ajax({
	    	type:'post',
	    	url:"{% url 'hub:inventory-list' %}",
	    	data:{csrfmiddlewaretoken: document.getElementsByName('csrfmiddlewaretoken')[0].value, "response_data": JSON.stringify(stock_objs) },
	    	success:(response) =>{
	    		location.reload();
	    	},
	    	error:(error) =>{
	    		alert(error)
	    	}
	    })
	}
	else{
		alert("Issue needs to be mentioned for all the checked items");
		location.reload();
	}
})