requirejs.config({
    shim: {
        jquery: {
            exports: "$"
        },
        cookie: {
            exports: "Cookies"
        },
        bootstrap: {
            deps: ["jquery"]
        },
    },
    baseUrl: "/static/dashboard/js/app",
    paths: {
        app: '/static/dashboard/js/app',
        material: "/static/dashboard/js/vendor/material-components-web-11.0.0",
        jquery: "/static/dashboard/js/vendor/jquery-3.4.0.min",
        cookie: "/static/dashboard/js/vendor/js.cookie"
    }
});

requirejs(["material", "cookie", "jquery", "base"], function(mdc, Cookies) {
	console.log(mdc);
	
	const dialogs = mdc.dataTable.MDCDataTable.attachTo(document.getElementById('dialogs_table'));
	
	const addDialog = mdc.dialog.MDCDialog.attachTo(document.getElementById('add_dialog_dialog'));

	const deleteDialog = mdc.dialog.MDCDialog.attachTo(document.getElementById('confirm_delete_dialog'));

	const lockDialog = mdc.dialog.MDCDialog.attachTo(document.getElementById('lock_delete_dialog'));

	const addDialogName = mdc.textField.MDCTextField.attachTo(document.getElementById('new_dialog_name'));
	
	$("#fab_add_dialog").click(function(eventObj) {
		addDialogName.value = '';
		
		$("#new_dialog_clone_id").val("");
		
		addDialog.open();
	});

	$(".dialog_clone_button").click(function(eventObj) {
		addDialogName.value = $(eventObj.target).data()['cloneName'];

		$("#new_dialog_clone_id").val($(eventObj.target).data()['cloneId']);
		
		addDialog.open();
	});

	$(".dialog_delete_button").click(function(eventObj) {
		$("#delete_dialog_name").text($(eventObj.target).data()["deleteName"]);
		$("#delete_dialog_id").val($(eventObj.target).data()["deleteId"]);

		deleteDialog.open()
	});

	$(".dialog_lock_button").click(function(eventObj) {
		lockDialog.open();
	});

	deleteDialog.listen('MDCDialog:closed', function(event) {
		action = event.detail['action'];
		
		if (action == 'close') {
		
		} else if (action == 'delete') {
			var deleteId = $("#delete_dialog_id").val();

			$.post('/dashboard/delete', {
				'identifier': deleteId
			}, function(data) {
				 location.reload(); 
			});
		}
	});

	addDialog.listen('MDCDialog:closed', function(event) {
		action = event.detail['action'];
		
		if (action == 'close') {
		
		} else if (action == 'create') {
			var cloneId = $("#new_dialog_clone_id").val();
			
			$.post('/dashboard/create', {
				'name': addDialogName.value,
				'identifier': cloneId
			}, function(data) {
				 location.reload(); 
			});
		}
	});

	const startDialog = mdc.dialog.MDCDialog.attachTo(document.getElementById('start_dialog_dialog'));

	const startDestination = mdc.textField.MDCTextField.attachTo(document.getElementById('session_destination'));

	startDialog.listen('MDCDialog:closed', function(event) {
		action = event.detail['action'];
		
		if (action == 'close') {
		
		} else if (action == 'start') {
			var startId = $("#start_dialog_id").val();
			
			$.post('/dashboard/start', {
				'destination': startDestination.value,
				'identifier': startId
			});
		}
	});

	$(".dialog_start_button").click(function(eventObj) {
		startDestination.value = '';

		$("#start_dialog_id").val($(eventObj.target).data()['startId']);
		
		startDialog.open();
	});
});