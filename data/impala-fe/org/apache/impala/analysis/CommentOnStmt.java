// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.

package org.apache.impala.analysis;

import org.apache.impala.common.AnalysisException;
import org.apache.impala.thrift.TCommentOnParams;
import org.apache.impala.util.MetaStoreUtil;

/**
 * A base class for COMMENT ON statement.
 */
public abstract class CommentOnStmt extends StatementBase {
  protected final String comment_;

  public CommentOnStmt(String comment) {
    comment_ = comment;
  }

  @Override
  public void analyze(Analyzer analyzer) throws AnalysisException {
    if (comment_ != null && comment_.length() > MetaStoreUtil.CREATE_MAX_COMMENT_LENGTH) {
      throw new AnalysisException(String.format("Comment exceeds maximum length of %d " +
          "characters. The given comment has %d characters.",
          MetaStoreUtil.CREATE_MAX_COMMENT_LENGTH, comment_.length()));
    }
  }

  public TCommentOnParams toThrift() {
    TCommentOnParams params = new TCommentOnParams();
    params.setComment(comment_);
    return params;
  }
}
