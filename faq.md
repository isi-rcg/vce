---
title: FAQ
menu_order: 3
---

# Frequently Asked Questions

## How can I get help?

You can write to
<a href="mailto:paolieri@usc.edu">paolieri@usc.edu</a>
or create an issue ticket on the [issue tracker](https://github.com/isi-rcg/vce/issues) of VCE.


## How should I prepare my multi-satellite application for VCE?

For each node in the constellation (satellites and base stations), VCE
needs a valid Amazon machine image (AMI) and a command to start the
part of the application that should run on that node.

A simple approach is the following:
- Start a VM on AWS with an [Amazon Linux image](https://aws.amazon.com/amazon-linux-ami/#Amazon_Linux_AMI_IDs) in your region.
- Install and test the software necessary for all nodes.
- Create [your own AMI](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/creating-an-ami-ebs.html).

Then, you can use the ID of your own AMI and specify different
commands (`cmd`) for the different nodes of the constellation in the
VCE configuration.


## How can I see the output of my program after the simulation?

Before deleting the AWS stack, you can SSH into the VM of any node and
check the output of your program inside the file `cmd.out`.


## How can I see the recorded metrics?

You can create an SSH tunnel from your computer to the VCE server
running on AWS:

``` console
$ ssh -i ~/.ssh/paolieri.pem -NL 3000:localhost:3000 centos@54.242.51.197
```

You can now access Grafana (running on the VCE server in AWS) from
your computer by opening [http://localhost:3000](http://localhost:3000).
