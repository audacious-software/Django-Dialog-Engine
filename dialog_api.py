# pylint: disable=line-too-long

def identify_script_issues(script):
    issues = []

    for node in script.definition:
        if node['type'] == 'random-branch':
            actions = node.get('actions', [])

            node_name = node.get('name', None)
            node_id = node.get('id', None)

            if len(actions) == 0: # pylint: disable=len-as-condition
                issues.append(('error', 'Random branch node "%s" (%s) has no configured actions.' % (node_name, node_id),))
            else:
                for action in actions:
                    destination = action.get('action', None)

                    if destination is None:
                        issues.append(('error', 'Random branch node "%s" (%s) contains branch pointing to a null destination.' % (node_name, node_id,),))

                    if destination == node_id:
                        issues.append(('error', 'Random branch node "%s" (%s) contains branch pointing back to itself.' % (node_name, node_id,),))

    return issues
