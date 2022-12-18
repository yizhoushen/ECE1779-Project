// Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

var aws = require("aws-sdk");
var ses = new aws.SES({ region: "us-east-1" });
exports.handler = async function (event) {
  var params = {
    Destination: {
      ToAddresses: ["harry8220@outlook.com"],
    },
    Message: {
      Body: {
        Text: { Data: "This is a kindly reminder that you may have uploaded inappropriate pictures on our website. Please keep in mind that we do not accept any NSFW contents." },
      },

      Subject: { Data: "Inappropriate Pictures Warning!" },
    },
    Source: "zihejia365@163.com",
  };
 
  return ses.sendEmail(params).promise()
};